import time
import random
import threading
import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from ..common.node.raw import RawNode
from ..common.node.networking.layers.routing import node_handler
from ..common.node.networking.layers.plugins.regional_heartbeat_plugin import RegionalHeartbeatPlugin
from ..common.node.networking.layers.plugins.regional_leader_plugin import RegionalLeaderPlugin
from ..common.node.events.connect import NodeConnectionType
from ..common.sync.mdns import DnsEntry
from ..common.leader_elec.bullynode import BullyPeer
from ..common.patching.mpatch import ManagedState


def _source_manager() -> ManagedState:
    return ManagedState.from_dict(1, {
        "region_state": {
            "name": None,
            "state": {},
            "meta": {},
        }
    })


class RegionalNode(RawNode):
    def __init__(
        self,
        region_name: str,
        address: Tuple[str, int],
        capital_candidates: List[DnsEntry],
        interval_ms: int = 2000,
        network_name: Optional[str] = None,
        replica_peer_addresses: Optional[List[Tuple[str, str, int]]] = None,
    ):
        print(f'STARTING REGION')
        if region_name.strip().lower() == "capital":
            raise ValueError("Region name cannot be 'Capital' (reserved).")

        self.region_name = region_name
        self.network_name_override = network_name or region_name
        self.address = address
        self.capital_candidates = capital_candidates
        self.current_capital_name: Optional[str] = None
        self.interval_ms = interval_ms
        self._restored_once = False

        self.replica_peer_addresses = replica_peer_addresses or []
        self.replica_peer_names = [
            name for name, _, _ in self.replica_peer_addresses
            if name != self.network_name_override
        ]

        self.current_region_leader = (
            self.network_name_override if not self.replica_peer_addresses else None
        )
        self.is_region_leader = not bool(self.replica_peer_addresses)

        self.lock = threading.Lock()
        self.proxy_lock = threading.Lock()
        self.sync_event = threading.Event()

        self.replica_state = _source_manager()
        self.replica_ready_event = threading.Event()
        self.replica_ready_event.set()
        self.fast_forward_event = threading.Event()
        self.fast_forward_event.set()

        # NEW: election-readiness gate
        self.region_election_ready = not bool(self.replica_peer_addresses)

        super().__init__(network_name=self.network_name_override, address=address)
        self.ready_to_handle()
        self.sites = self.build_sites()

        self.regional_heartbeat_plugin = self.register_plugin(
            RegionalHeartbeatPlugin(host=self, interval_ms=1000)
        )

        if self.replica_peer_addresses:
            self.regional_leader_plugin = self.register_plugin(
                RegionalLeaderPlugin(
                    host=self,
                    node=BullyPeer(
                        name=self.network_name,
                        unique_id=self._unique_id_from_name(self.network_name),
                        priority=self._priority_from_site_count(),
                    ),
                    peers={
                        BullyPeer(
                            peer_name,
                            self._unique_id_from_name(peer_name),
                            self._priority_from_site_count(),
                        ): (peer_name, peer_ip, peer_port)
                        for peer_name, peer_ip, peer_port in self.replica_peer_addresses
                    },
                )
            )
        # print("REGION?????????")
        

    # -------------------------------------------------------------------------
    # Election participation gate
    # -------------------------------------------------------------------------
    def can_participate_in_region_election(self) -> bool:
        return self.region_election_ready

    @node_handler(internal_ms=250)
    def bootstrap_region_sync(self):
        if self.region_election_ready:
            return

        highest = None
        highest_version = -1

        for peer in self.replica_peer_names:
            if not self.has_connection(peer):
                addr = self._peer_addr_by_name(peer)
                if addr is not None:
                    try:
                        self._connect_to(addr)
                    except Exception:
                        continue

            if not self.has_connection(peer):
                continue

            try:
                vers = self.send_message(peer, "version", {}, timeout=1.0)["version"]
                if vers > highest_version:
                    highest = peer
                    highest_version = vers
            except Exception:
                continue

        if highest is None:
            return

        if highest_version > self.replica_state.version:
            self.__fast_forward_to_target(highest)

        self.current_region_leader = highest
        self.is_region_leader = False
        self.region_election_ready = True

    # -------------------------------------------------------------------------
    # RawNode compatibility helpers
    # -------------------------------------------------------------------------
    def _connect_to(self, address: tuple[str, int]):
        if hasattr(self, "connect") and callable(getattr(self, "connect")):
            return self.connect(address)
        if hasattr(self, "_net_connect") and callable(getattr(self, "_net_connect")):
            return self._net_connect(address)
        raise AttributeError("RawNode does not expose connect or _net_connect")

    def _disconnect_name(self, name: str):
        if hasattr(self, "disconnect") and callable(getattr(self, "disconnect")):
            return self.disconnect(name)
        if hasattr(self, "_net_disconnect") and callable(getattr(self, "_net_disconnect")):
            return self._net_disconnect(name)
        if hasattr(self, "connection_map"):
            try:
                return self.connection_map.deregister(name)
            except Exception:
                pass
        raise AttributeError("RawNode does not expose disconnect/_net_disconnect/connection_map.deregister")

    def _outbound_names(self) -> list[str]:
        if hasattr(self, "connection_map"):
            if hasattr(self.connection_map, "get_outbound_names"):
                return self.connection_map.get_outbound_names()
            if hasattr(self.connection_map, "get_connection_names"):
                return self.connection_map.get_connection_names()
        return []

    def _priority_from_site_count(self) -> int:
        return len(self.sites)

    def _unique_id_from_name(self, name: str) -> str:
        return f"{name}-uid"

    def _peer_addr_by_name(self, peer_name: str):
        for name, host, port in self.replica_peer_addresses:
            if name == peer_name:
                return (host, port)
        return None

    def _print_state_hash(self):
        serialized = json.dumps(
            obj=self.replica_state.inspect_dict(),
            default=lambda x: str(x),
            sort_keys=True,
        )
        role = "leader" if self.is_region_leader else "follower"
        print(
            f"[{self.network_name} | {role}] version={self.replica_state.version}, "
            f"data={hashlib.sha256(serialized.encode()).hexdigest()}"
        )

    def multicast_region_replicas(self, route: str, body: dict):
        for peer_name in self.replica_peer_names:
            if not self.has_connection(peer_name):
                addr = self._peer_addr_by_name(peer_name)
                if addr is not None:
                    try:
                        self._connect_to(addr)
                    except Exception:
                        continue
            try:
                self.send_message(peer_name, route, body, timeout=1.0)
            except Exception:
                try:
                    if self.has_connection(peer_name):
                        self._disconnect_name(peer_name)
                except Exception:
                    pass

    # -------------------------------------------------------------------------
    # Region leader callbacks
    # -------------------------------------------------------------------------
    def on_start_region_election(self):
        pass

    def on_become_region_leader(self):
        self.fast_forward_event.clear()
        try:
            self.current_region_leader = self.network_name
            self.is_region_leader = True

            versions = {}
            for peer in self.replica_peer_names:
                if peer == self.network_name:
                    continue

                if not self.has_connection(peer):
                    addr = self._peer_addr_by_name(peer)
                    if addr is not None:
                        try:
                            self._connect_to(addr)
                        except Exception:
                            pass

                if not self.has_connection(peer):
                    continue

                try:
                    vers = self.send_message(peer, "version", {}, timeout=1.0)["version"]
                    versions[peer] = vers
                except Exception:
                    try:
                        if self.has_connection(peer):
                            self._disconnect_name(peer)
                    except Exception:
                        pass

            if versions:
                target, top_version = max(versions.items(), key=lambda x: x[1])
                if self.replica_state.version < top_version:
                    self.__fast_forward_to_target(target)
        finally:
            self.region_election_ready = True
            self.fast_forward_event.set()
            self.replica_ready_event.set()

    def on_elect_region_leader(self, _leader, _peer, target):
        self.current_region_leader = target
        self.is_region_leader = (target == self.network_name)

        if self.is_region_leader:
            self.region_election_ready = True
            self.replica_ready_event.set()
            return

        try:
            vers = self.send_message(target, "version", {}, timeout=1.0)["version"]
        except Exception:
            print(f"[{self.network_name}] Could not reach regional leader {target} for version check.")
            return

        if vers > self.replica_state.version:
            self.__fast_forward_to_target(target)

        self.region_election_ready = True
        self.replica_ready_event.set()

    # -------------------------------------------------------------------------
    # Region replica versioning / sync
    # -------------------------------------------------------------------------
    @node_handler(name="version")
    def handle_version(self, _body):
        return {"version": self.replica_state.version}

    @node_handler(name="fast.forward")
    def handle_fast_forward(self, _body):
        return {
            "__version": self.replica_state.version,
            "__state": self.replica_state.inspect_dict(),
        }

    def __fast_forward_to_target(self, target: str):
        rs = self.send_message(target, "fast.forward", {}, timeout=2.0)
        self.replica_state.fast_forward(rs["__version"], rs["__state"])
        self._print_state_hash()

    def __commit_local_replica(self, tx_data: dict):
        result = self.replica_state.end_transaction(tx_data, apply=True)
        self._print_state_hash()
        return result

    def __proxy_call(self, call, proxy_name: str, data: dict):
        with self.proxy_lock:
            _, result = call(data, None)
            if result is not None:
                self.multicast_region_replicas(proxy_name, dict(data))
        return {"status": "success"}

    def apply_region_local_state(self, data: dict):
        with self.lock:
            tx = self.replica_state.start_transaction()
            tx["region_state"] = {
                "name": data["name"],
                "state": data["state"],
                "meta": data["meta"],
            }
            return data["name"], self.__commit_local_replica(tx)

    def __handle_region_local_state(self, data, _src):
        return self.apply_region_local_state(data)

    @node_handler(name="api.proxy.region.state_update")
    def handle_region_local_state_proxy(self, data):
        self.__handle_region_local_state(data, None)
        return {"status": "success"}

    # -------------------------------------------------------------------------
    # Capital connectivity / leader discovery / recovery
    # -------------------------------------------------------------------------
    @node_handler(internal_ms=500)
    def connect_to_any_capital_candidate(self):
        for addr in self.capital_candidates:
            try:
                if not self.has_connection(addr.name):
                    self._connect_to((addr.ip, addr.port))
                    print(f"[{self.region_name}] connected to candidate capital at {addr}")
            except Exception as e:
                print(f"[{self.region_name}] failed to connect to {addr.name}: {type(e).__name__}: {e}")

        if not self.current_capital_name or not self.has_connection(self.current_capital_name):
            self._discover_leader()

        if self.current_capital_name and not self._restored_once:
            if self.restore_from_capital():
                self._restored_once = True

    def _discover_leader(self):
        found_leader = None

        for name in self._outbound_names():
            if not name.startswith("rm-"):
                continue
            if not self.has_connection(name):
                continue

            try:
                resp = self.send_message(name, "api.who_is_leader", {}, timeout=1.0)
                leader = resp.get("leader")
                is_leader = resp.get("is_leader", False)

                leader_name = leader
                if isinstance(leader, dict):
                    leader_name = leader.get("name")

                if is_leader and leader_name == name:
                    found_leader = leader_name
                    break

            except Exception as e:
                print(f"[{self.region_name}] leader probe to {name} failed: {type(e).__name__}: {e}")
                continue

        self.current_capital_name = found_leader

        if found_leader:
            print(f"[{self.region_name}] discovered leader {found_leader}")
        else:
            print(f"[{self.region_name}] no leader discovered from current capital candidates")

        return found_leader

    def _send_to_capital(self, method: str, body: dict):
        if not self.is_region_leader:
            return None

        if not self.current_capital_name or not self.has_connection(self.current_capital_name):
            self.current_capital_name = None
            self._discover_leader()

        if not self.current_capital_name:
            print(f"[{self.region_name}] no known capital leader for {method}")
            return None

        try:
            return self.send_message(
                target=self.current_capital_name,
                method=method,
                body=body,
                timeout=1.0,
            )
        except Exception as e:
            dead_leader = self.current_capital_name
            print(f"[{self.region_name}] send to {dead_leader} failed: {type(e).__name__}: {e}")

            try:
                if self.has_connection(dead_leader):
                    self._disconnect_name(dead_leader)
            except Exception:
                pass

            self.current_capital_name = None
            self._discover_leader()

            if not self.current_capital_name:
                print(f"[{self.region_name}] retry failed: no leader available for {method}")
                return None

            try:
                return self.send_message(
                    target=self.current_capital_name,
                    method=method,
                    body=body,
                    timeout=1.0,
                )
            except Exception as e2:
                print(f"[{self.region_name}] retry to {self.current_capital_name} failed: {type(e2).__name__}: {e2}")
                try:
                    if self.has_connection(self.current_capital_name):
                        self._disconnect_name(self.current_capital_name)
                except Exception:
                    pass

                self.current_capital_name = None
                return None

    def restore_from_capital(self):
        if not self.current_capital_name:
            return False

        try:
            resp = self.send_message(
                self.current_capital_name,
                "api.get_region_state",
                {"name": self.region_name},
                timeout=1.0,
            )
        except Exception as e:
            print(f"[{self.region_name}] failed to restore state from capital: {type(e).__name__}: {e}")
            return False

        if resp.get("status") != "success":
            print(f"[{self.region_name}] no previous saved state available")
            return False

        data = resp.get("data", {})
        meta = data.get("meta", {})
        sites = meta.get("sites", [])

        site_map = {s.get("name"): s for s in sites if isinstance(s, dict)}
        for local_site in self.sites:
            local_name = getattr(local_site, "name", None)
            if local_name in site_map:
                restored = site_map[local_name]
                if "resource_value" in restored:
                    local_site.resource_value = restored["resource_value"]

        with self.lock:
            tx = self.replica_state.start_transaction()
            tx["region_state"] = {
                "name": self.region_name,
                "state": data.get("state", {}),
                "meta": meta,
            }
            self.__commit_local_replica(tx)

        print(f"[{self.region_name}] restored previous state from capital {self.current_capital_name}")
        return True

    @abstractmethod
    def build_sites(self) -> List[Any]:
        raise NotImplementedError

    @abstractmethod
    def aggregate_state(self) -> Dict[str, Any]:
        raise NotImplementedError

    def simulate_tick(self) -> None:
        for s in self.sites:
            t = getattr(s, "resource_type", "")
            if t == "Powerplant":
                s.resource_value = random.choices(
                    ["stable", "unstable", "down"],
                    [0.75, 0.20, 0.05]
                )[0]
            elif t == "Railroad":
                s.resource_value = random.choices(
                    ["operational", "degraded", "down"],
                    [0.75, 0.20, 0.05]
                )[0]
            elif t in ["Hospital", "Fuel Depot", "Water Treatment Plant"]:
                cur = int(s.resource_value)
                delta = random.randint(-3, 2)
                s.resource_value = max(0, min(100, cur + delta))

    def sites_snapshot(self) -> List[Dict[str, Any]]:
        snap = []
        for s in self.sites:
            if hasattr(s, "to_dict") and callable(getattr(s, "to_dict")):
                snap.append(s.to_dict())
            else:
                snap.append({
                    "name": getattr(s, "name", "unknown"),
                    "region_name": getattr(s, "region_name", self.region_name),
                    "resource_type": getattr(s, "resource_type", "unknown"),
                    "resource_value": getattr(s, "resource_value", None),
                })
        return snap

    def heartbeat_payload(self) -> Dict[str, Any]:
        return {
            "name": self.region_name,
            "state": self.aggregate_state(),
            "meta": {
                "timestamp": time.time(),
                "region_type": self.__class__.__name__,
                "sites": self.sites_snapshot(),
            },
        }

    def infra_addr(self, site_id: str, host="127.0.0.1", base_port=32000, span=4000):
        key = f"{self.network_name}:{site_id}"
        h = 0
        for ch in key:
            h = (h * 31 + ord(ch)) % span
        return (host, base_port + h)

    @node_handler(name="region.ping")
    def ping(self, _message: dict):
        return {
            "pong": True,
            "region": self.region_name,
            "replica": self.network_name,
            "is_region_leader": self.is_region_leader,
            "regional_leader": self.current_region_leader,
            "version": self.replica_state.version,
        }

    @node_handler(name="api.report")
    def handle_report(self, msg: dict):
        site_name = msg.get("name")
        for s in self.sites:
            if getattr(s, "name", None) == site_name:
                s.resource_value = msg.get("resource_value")
                break
        return {"status": "ok"}

    @node_handler(on_connect=NodeConnectionType.OUTBOUND)
    def on_outbound_connect(self, name: str):
        print(f"[{self.region_name}] outbound connected to {name}")

    @node_handler(on_disconnect=NodeConnectionType.OUTBOUND)
    def on_outbound_disconnect(self, name: str):
        print(f"[{self.region_name}] outbound disconnected from {name}")

    def tick_and_send(self) -> None:
        if not self.is_region_leader:
            return

        self.replica_ready_event.wait()
        self.fast_forward_event.wait()

        self.simulate_tick()
        state = self.aggregate_state()
        payload = {
            "name": self.region_name,
            "state": state,
            "meta": {
                "region_type": self.__class__.__name__,
                "sites": self.sites_snapshot(),
            },
        }

        self.__proxy_call(
            call=self.__handle_region_local_state,
            proxy_name="api.proxy.region.state_update",
            data=payload,
        )

        self._send_to_capital(
            method="api.update_state",
            body={
                "name": self.region_name,
                "state": {
                    "state": state,
                    "meta": payload["meta"],
                },
            }
        )

    def shutdown(self):
        for site in getattr(self, "sites", []):
            try:
                site.shutdown()
            except Exception:
                pass
        return super().shutdown()