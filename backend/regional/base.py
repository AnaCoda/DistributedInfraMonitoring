import time
import random
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from ..common.node.raw import RawNode
from ..common.node.networking.layers.routing import node_handler
from ..common.node.networking.layers.plugins.regional_heartbeat_plugin import RegionalHeartbeatPlugin
from ..common.node.events.connect import NodeConnectionType
from ..common.sync.mdns import DnsEntry


class RegionalNode(RawNode, ABC):
    """
    Regional node that:
    - listens on its own address
    - connects to candidate capital replicas
    - discovers the currently active capital leader
    - restores prior state from the capital on restart
    - periodically sends heartbeats + state updates
    """

    def __init__(
        self,
        region_name: str,
        address: Tuple[str, int],
        capital_candidates: List[DnsEntry],
        interval_ms: int = 2000,
    ):
        if region_name.strip().lower() == "capital":
            raise ValueError("Region name cannot be 'Capital' (reserved).")

        self.region_name = region_name
        self.address = address
        self.capital_candidates = capital_candidates
        self.current_capital_name: Optional[str] = None
        self.interval_ms = interval_ms
        self._restored_once = False

        super().__init__(network_name=region_name, address=address)

        self._trigger_map: dict[str, threading.Event] = {}
        self._trigger_lock = threading.Lock()

        self.sites = self.build_sites()

        self.regional_heartbeat_plugin = self.register_plugin(
            RegionalHeartbeatPlugin(host=self, interval_ms=1000)
        )

    def set_trigger(self, name: str):
        with self._trigger_lock:
            ev = self._trigger_map.get(name)
            if ev is None:
                ev = threading.Event()
                self._trigger_map[name] = ev
            ev.set()

    def wait_trigger(self, name: str, timeout: float | None = None):
        with self._trigger_lock:
            ev = self._trigger_map.get(name)
            if ev is None:
                ev = threading.Event()
                self._trigger_map[name] = ev
        return ev.wait(timeout=timeout)

    def clear_trigger(self, name: str):
        with self._trigger_lock:
            ev = self._trigger_map.get(name)
            if ev is None:
                ev = threading.Event()
                self._trigger_map[name] = ev
            ev.clear()

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
        key = f"{self.region_name}:{site_id}"
        h = 0
        for ch in key:
            h = (h * 31 + ord(ch)) % span
        return (host, base_port + h)

    @node_handler(name="region.ping")
    def ping(self, _message: dict):
        return {"pong": True, "region": self.network_name}

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
        self.simulate_tick()
        state = self.aggregate_state()

        self._send_to_capital(
            method="api.update_state",
            body={
                "name": self.region_name,
                "state": {
                    "state": state,
                    "meta": {
                        "region_type": self.__class__.__name__,
                        "sites": self.sites_snapshot(),
                    },
                },
            }
        )