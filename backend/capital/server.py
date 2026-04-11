from ..common.node.raw import RawNode
from ..common.node.networking.layers.routing import node_handler
from ..common.node.events.connect import NodeConnectionType

from ..common.patching.mpatch import ManagedState, VersionedPatch
from ..shared.leader_election import BullyElectionMixin

import threading
import datetime
import time
import hashlib
import json

from ..common.sync.signal import HoldSignal


def _source_manager() -> ManagedState:
    state_infrastructure = {
        "power": "stable",
        "medical_capacity": 100,
        "transport": "operational",
        "water_capacity": 100,
        "fuel_storage": 100,
    }
    return ManagedState.from_dict(1, {
        "heartbeat": {},
        "state": {
            "Capital": {
                "state": state_infrastructure,
                "meta": {
                    "region_type": "CapitalNode",
                    "sites": []
                }
            }
        }
    })


from ..common.leader_elec.bullynode import BullyPeer


class CapitalNode(BullyElectionMixin, RawNode):
    def __init__(
        self,
        network_name: str,
        address: tuple[str, int],
        peer_addresses: list[tuple[str, str, int]],
        seed_leader_name: str | None = None,
        bootstrap_leader: bool = False,
    ):
        self.peer_addresses = peer_addresses
        self.peer_names = [name for name, _, _ in peer_addresses if name != network_name]

        self.node_id = self._node_id_from_name(network_name)

        self.last_leader_heartbeat = time.time()
        self.leader_timeout_ms = 3000

        self.election_lock = threading.Lock()
        self.election_in_progress = False
        self.received_ok = False
        self.awaiting_coordinator = False
        self.coordinator_deadline = None

        self.lock = threading.Lock()
        self.proxy_lock = threading.Lock()

        self.replica_state = _source_manager()
        self.ready = bootstrap_leader
        self.ready_evt = threading.Event()
        if self.ready:
            self.ready_evt.set()

        self.sync_event = threading.Event()
        self.address = address
        
        super().__init__(network_name=network_name, address=address)

        self._trigger_map: dict[str, threading.Event] = {}
        self._trigger_lock = threading.Lock()

        self.init_bully_election(
            node=BullyPeer(
                name=self.network_name,
                id=self._node_id_from_name(self.network_name)
            ),
            peer_names={
                BullyPeer(peer_name, self._node_id_from_name(peer_name)): (peer_name, peer_ip, peer_port)
                for peer_name, peer_ip, peer_port in peer_addresses
            }
        )

        self.ready_signal = HoldSignal()
        self.fast_forward = HoldSignal()

    # -------------------------------------------------------------------------
    # Trigger compatibility helpers
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _node_id_from_name(self, name: str) -> int:
        try:
            return int(name.split("-")[-1])
        except Exception:
            return -1

    def _peer_addr_by_name(self, peer_name: str):
        for name, host, port in self.peer_addresses:
            if name == peer_name:
                return (host, port)
        return None

    def _print_state_hash(self):
        serialized = json.dumps(
            obj=self.replica_state.inspect_dict(),
            default=lambda x: str(x),
            sort_keys=True,
        )
        role = "leader" if self.node.is_leader() else "follower"
        print(
            f"[{self.network_name} | {role}] version={self.replica_state.version}, "
            f"data={hashlib.sha256(serialized.encode()).hexdigest()}"
        )

    def multicast(self, target_glob: str, route: str, body: dict, include_self: bool = False):
        prefix = target_glob[:-1] if target_glob.endswith("*") else target_glob
        for name in self._outbound_names():
            if not include_self and name == self.network_name:
                continue
            if not name.startswith(prefix):
                continue
            try:
                self.send_message(name, route, body, timeout=1.0)
            except Exception:
                try:
                    if self.has_connection(name):
                        self._disconnect_name(name)
                except Exception:
                    pass

    @node_handler(internal_ms=500)
    def maintain_peer_links(self):
        for peer_name, peer_ip, peer_port in self.peer_addresses:
            if peer_name == self.network_name:
                continue
            if self.has_connection(peer_name):
                continue
            try:
                self._connect_to((peer_ip, peer_port))
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # State replication
    # -------------------------------------------------------------------------
    @node_handler(name='fast.forward')
    def handle_fast_forward(self, _message):
        return {
            "__version": self.replica_state.version,
            "__state": self.replica_state.inspect_dict()
        }

    @node_handler(name='version')
    def handle_version(self, _):
        return {
            "version": self.replica_state.version
        }

    def on_start_election(self):
        pass

    def on_become_leader(self):
        print("BECAME LEADER!!")
        print(f'[{self.network_name}] Release.')
        self.fast_forward.hold()
        try:
            versions = {}
            for peer in self.peer_names:
                if peer == self.network_name:
                    continue

                if not self.has_connection(peer):
                    for (a, b, c) in self.peer_addresses:
                        if a == peer:
                            try:
                                self._connect_to((b, c))
                            except Exception:
                                pass

                if not self.has_connection(peer):
                    continue

                try:
                    vers = self.send_message(peer, 'version', {}, timeout=1.0)['version']
                    versions[peer] = vers
                except Exception:
                    try:
                        if self.has_connection(peer):
                            self._disconnect_name(peer)
                    except Exception:
                        pass
                    continue

            versions = list(versions.items())
            versions.sort(key=lambda x: x[1], reverse=True)

            if len(versions) > 0:
                name, top_version = versions[0]
                if self.replica_state.version < top_version:
                    print(f'[{self.network_name}] Leader fast forwarded to more up-to-date replica {name}')
                    self.__fast_forward_to_target(name)
            print(f'Versions: {versions}')
        finally:
            self.fast_forward.ready()
            self.ready_signal.ready()

    def __fast_forward_to_target(self, target: str):
        rs = self.send_message(target, "fast.forward", {}, timeout=2.0)
        self.replica_state.fast_forward(rs["__version"], rs["__state"])

    def on_elect_leader(self, leader, peer, target):
        try:
            vers = self.send_message(target, 'version', {}, timeout=1.0)['version']
        except Exception:
            print(f'[{self.network_name}] Could not reach leader {target} for version check.')
            return

        if vers > self.replica_state.version:
            print(f'[{self.network_name}] Requires a fast forward to version {vers}.')
            self.__fast_forward_to_target(target)

        print(f'[{self.network_name}] Release.')
        self.ready_signal.ready()

    def __commit_local_replica(self, tx_data: dict):
        result = self.replica_state.end_transaction(tx_data, apply=True)
        self._print_state_hash()
        return result

    def __proxy_call(self, call, proxy_name: str, data, source=None):
        with self.proxy_lock:
            _, result = call(data, source)
            if result is not None:
                self.multicast('rm-*', proxy_name, data, include_self=False)
        return {"status": "success"}

    # -------------------------------------------------------------------------
    # Region heartbeat + state update handling
    # -------------------------------------------------------------------------
    def __handle_heartbeat(self, _data, source: str):
        state = self.replica_state.start_transaction()
        if source not in state['heartbeat']:
            state['heartbeat'][source] = {}
        state['heartbeat'][source]['last_contact'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return None, self.__commit_local_replica(state)

    def __handle_operation(self, data, _src):
        self.ready_signal.barrier()
        state_name = data["name"]
        state_data = data["state"]

        if not state_name or not state_data:
            raise RuntimeError("Missing name or state.")

        with self.lock:
            tx = self.replica_state.start_transaction()
            tx['state'][state_name] = state_data
            rs = self.__commit_local_replica(tx)
            return state_name, rs

    @node_handler(name='api.proxy.region.heartbeat')
    def handle_region_heartbeat_proxy(self, message: dict, source: str):
        print(f'[{self.network_name}] Received proxied from {source}')
        self.__handle_heartbeat(message, source)
        return {"status": "success"}

    @node_handler(name='api.region.heartbeat')
    def handle_region_heartbeat(self, message: dict, source: str):
        if not self.node.is_leader():
            return {
                "status": "fail",
                "reason": f"not leader; current leader is {self.current_leader}"
            }

        return self.__proxy_call(
            call=self.__handle_heartbeat,
            proxy_name='api.proxy.region.heartbeat',
            data=message,
            source=source
        )

    @node_handler(name='api.proxy.state_update')
    def handle_operation_proxy(self, data):
        state_name, _ = self.__handle_operation(data, None)
        return {"message": f"State {state_name} updated successfully."}

    @node_handler(name="api.update_state")
    def update_state(self, data):
        self.ready_signal.barrier()
        if not self.node.is_leader():
            return {
                "status": "fail",
                "reason": f"not leader; current leader is {self.current_leader}"
            }

        self.current_capital = self.network_name
        self.current_leader = self.network_name
        self.is_capital = True
        self.is_leader = True

        return self.__proxy_call(
            call=self.__handle_operation,
            proxy_name='api.proxy.state_update',
            data=data
        )

    # -------------------------------------------------------------------------
    # Reads / recovery
    # -------------------------------------------------------------------------
    @node_handler(name="api.national_infrastructure")
    def get_national_status(self, _m):
        self.ready_signal.barrier()

        while not self.replica_state.is_consistent():
            self.sync_event.wait()

        return {
            "__version": self.replica_state.version,
            "__state": self.replica_state.inspect_dict(),
            "leader": self.current_leader,
            "capital": self.current_capital,
        }

    @node_handler(name="api.get_region_state")
    def get_region_state(self, body: dict, _sender: str):
        region_name = body.get("name")
        if not region_name:
            return {"status": "fail", "reason": "missing region name"}

        state = self.replica_state.inspect_dict()
        region_state = state.get("state", {}).get(region_name)

        if region_state is None:
            return {"status": "fail", "reason": f"no saved state for region {region_name}"}

        return {
            "status": "success",
            "region": region_name,
            "data": region_state,
            "leader": self.current_leader,
            "capital": self.current_capital,
            "version": self.replica_state.version,
        }