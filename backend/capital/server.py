from ..shared.node import NodeBase, node_handler, NodeConnectionType
from ..common.patching.mpatch import ManagedState, VersionedPatch
from ..shared.leader_election import BullyElectionMixin

import threading
import datetime
import time
import hashlib
import json


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


class CapitalNode(BullyElectionMixin, NodeBase):
    def __init__(
        self,
        network_name: str,
        address: tuple[str, int],
        peer_addresses: list[tuple[str, str, int]],
        seed_leader_name: str | None = None,
        bootstrap_leader: bool = False,
    ):
        # ---- Election/bootstrap fields BEFORE NodeBase starts interval handlers ----
        self.peer_addresses = peer_addresses
        self.peer_names = [name for name, _, _ in peer_addresses if name != network_name]

        self.node_id = self._node_id_from_name(network_name)

        self.is_leader = bootstrap_leader
        self.current_leader = network_name if bootstrap_leader else seed_leader_name

        self.is_capital = bootstrap_leader
        self.current_capital = network_name if bootstrap_leader else seed_leader_name

        self.last_leader_heartbeat = time.time()
        self.leader_timeout_ms = 3000

        self.election_lock = threading.Lock()
        self.election_in_progress = False
        self.received_ok = False
        self.awaiting_coordinator = False
        self.coordinator_deadline = None

        # ---- Capital replication state ----
        self.lock = threading.Lock()
        self.proxy_lock = threading.Lock()

        self.replica_state = _source_manager()
        self.ready = bootstrap_leader
        self.ready_evt = threading.Event()
        if self.ready:
            self.ready_evt.set()

        self.sync_event = threading.Event()

        super().__init__(network_name=network_name, address=address)

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
        role = "leader" if self.is_leader else "follower"
        print(
            f"[{self.network_name} | {role}] version={self.replica_state.version}, "
            f"data={hashlib.sha256(serialized.encode()).hexdigest()}"
        )
    
    def multicast(self, target_glob: str, route: str, body: dict, include_self: bool = False):
        prefix = target_glob[:-1] if target_glob.endswith("*") else target_glob
        for name in list(self.outbound_connections.keys()):
            if not include_self and name == self.network_name:
                continue
            if not name.startswith(prefix):
                continue
            try:
                self.send_message(name, route, body, timeout=1.0)
            except Exception:
                try:
                    if self.has_connection(name):
                        self.disconnect(name)
                except Exception:
                    pass

    def discover_current_leader(self):
        for peer in self.connected_peer_names():
            try:
                resp = self.send_message(peer, "api.who_is_leader", {}, timeout=1.0)
                leader = resp.get("leader")
                is_leader = resp.get("is_leader", False)

                if is_leader and leader == peer:
                    self.current_leader = leader
                    self.current_capital = leader
                    self.is_leader = (leader == self.network_name)
                    self.is_capital = (leader == self.network_name)
                    self.last_leader_heartbeat = time.time()
                    self.election_in_progress = False
                    self.awaiting_coordinator = False
                    self.coordinator_deadline = None
                    self.received_ok = False
                    print(f"[{self.network_name}] discovered active leader {leader}")
                    return leader
            except Exception:
                try:
                    if self.has_connection(peer):
                        self.disconnect(peer)
                except Exception:
                    pass
                continue
        return None

    def _bootstrap_sync_from_leader(self):
        if not self.current_leader or self.current_leader == self.network_name:
            self.ready = True
            self.ready_evt.set()
            return

        if not self.has_connection(self.current_leader):
            return

        try:
            rs = self.send_message(self.current_leader, "fast.forward", {}, timeout=2.0)
            self.replica_state.fast_forward(rs["__version"], rs["__state"])
            self.ready = True
            self.ready_evt.set()
            print(f"[{self.network_name}] Fast-forwarded to version={self.replica_state.version}")
            self._print_state_hash()
        except Exception as e:
            print(f"[{self.network_name}] failed bootstrap sync from leader: {e}")

    def _start(self):
        for peer_name, host, port in self.peer_addresses:
            if peer_name == self.network_name:
                continue
            try:
                self.connect((host, port))
                print(f"[{self.network_name}] connected to peer {peer_name}")
            except Exception as e:
                print(f"[{self.network_name}] could not connect to peer {peer_name}: {e}")

        time.sleep(1)

        leader = self.discover_current_leader()
        if leader:
            self._bootstrap_sync_from_leader()
            return

        self.start_election()

    # -------------------------------------------------------------------------
    # Leader election hooks / ticks
    # -------------------------------------------------------------------------
    def on_become_leader(self):
        self.is_leader = True
        self.current_leader = self.network_name
        self.is_capital = True
        self.current_capital = self.network_name
        self.ready = True
        self.ready_evt.set()
        print(f"[{self.network_name}] became leader / capital")

    def on_new_leader(self, leader):
        self.is_leader = (leader == self.network_name)
        self.current_leader = leader
        self.is_capital = (leader == self.network_name)
        self.current_capital = leader
        print(f'[{self.network_name}] acknowledging {leader} as leader/capital')

    @node_handler(name="api.who_is_leader")
    def who_is_leader(self, _body: dict):
        return {
            "leader": self.current_leader,
            "is_leader": self.is_leader,
            "capital": self.current_capital,
            "is_capital": self.is_capital,
            "self": self.network_name,
        }

    @node_handler(name="api.who_is_capital")
    def who_is_capital(self, _body: dict):
        return {
            "capital": self.current_capital,
            "is_capital": self.is_capital,
            "leader": self.current_leader,
            "is_leader": self.is_leader,
            "self": self.network_name,
        }

    @node_handler(internal_ms=1000)
    def election_tick(self):
        if not hasattr(self, "is_leader"):
            return
        self.step_election()

    @node_handler(internal_ms=2000)
    def peer_reconnect_tick(self):
        for peer_name, host, port in self.peer_addresses:
            if peer_name == self.network_name:
                continue

            if self.has_connection(peer_name):
                continue

            try:
                self.connect((host, port))
                print(f"[{self.network_name}] reconnected to peer {peer_name}")
            except Exception:
                try:
                    if self.has_connection(peer_name):
                        self.disconnect(peer_name)
                except Exception:
                    pass

    @node_handler(internal_ms=2500)
    def leader_sync_tick(self):
        if not self.is_leader:
            self.try_refresh_from_leader()

    def try_refresh_from_leader(self):
        if not self.current_leader or self.current_leader == self.network_name:
            return

        if not self.has_connection(self.current_leader):
            return

        try:
            resp = self.send_message(self.current_leader, "api.national_infrastructure", {}, timeout=1.5)
            self.replica_state.fast_forward(resp["__version"], resp["__state"])
            self.current_capital = resp.get("capital", self.current_capital)
            self.current_leader = resp.get("leader", self.current_leader)
            self.is_leader = False
            self.is_capital = False
            self.ready = True
            self.ready_evt.set()
            self.sync_event.set()
            self._print_state_hash()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # State replication
    # -------------------------------------------------------------------------
    @node_handler(name='fast.forward')
    def handle_fast_forward(self, _message):
        return {
            "__version": self.replica_state.version,
            "__state": self.replica_state.inspect_dict(),
            "leader": self.current_leader,
            "capital": self.current_capital,
        }

    @node_handler(name='push.state_patch')
    def handle_state_update(self, body: dict, sender: str):
        version = VersionedPatch.from_dict(body)
        self.replica_state.apply_update(version)

        self._print_state_hash()

        if self.replica_state.is_consistent():
            self.sync_event.set()
            self.ready = True
            self.ready_evt.set()

        return {"status": "success"}

    def __commit_local_replica(self, tx_data: dict):
        result = self.replica_state.end_transaction(tx_data, apply=True)
        self._print_state_hash()
        return result

    def __proxy_call(self, call, proxy_name: str, data, source=None):
        with self.proxy_lock:
            _, result = call(data, source)
            if result is not None:
                self.multicast('rm-*', proxy_name, result, include_self=False)
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
        self.__handle_heartbeat(message, source)
        return {"status": "success"}

    @node_handler(name='api.region.heartbeat')
    def handle_region_heartbeat(self, message: dict, source: str):
        if not self.is_leader:
            return {
                "status": "fail",
                "reason": f"not leader; current leader is {self.current_leader}"
            }

        self.current_capital = self.network_name
        self.current_leader = self.network_name
        self.is_capital = True
        self.is_leader = True

        return self.__proxy_call(
            call=self.__handle_heartbeat,
            proxy_name='push.state_update',
            data=message,
            source=source
        )

    @node_handler(name='api.proxy.state_update')
    def handle_operation_proxy(self, data):
        state_name, _ = self.__handle_operation(data, None)
        return {"message": f"State {state_name} updated successfully."}

    @node_handler(name="api.update_state")
    def update_state(self, data):
        if not self.is_leader:
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
            proxy_name='push.state_update',
            data=data
        )

    # -------------------------------------------------------------------------
    # Reads / recovery
    # -------------------------------------------------------------------------
    @node_handler(name="api.national_infrastructure")
    def get_national_status(self, _m):
        while not self.ready:
            self.ready_evt.wait()

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