from ..shared.node import NodeBase, node_handler, NodeConnectionType
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

        # self.is_leader = bootstrap_leader
        # self.current_leader = network_name if bootstrap_leader else seed_leader_name

        # self.is_capital = bootstrap_leader
        # self.current_capital = network_name if bootstrap_leader else seed_leader_name

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
        for name in self.connection_map.get_outbound_names():
            # print(f'Trying to multicast to {name}')
            if not include_self and name == self.network_name:
                continue
            if not name.startswith(prefix):
                continue
            # print(f'Can multicast to {name}')
            try:
                self.send_message(name, route, body, timeout=1.0)
            except Exception:
                pass
                # try:
                #     if self.has_connection(name):
                #         print(f'[{self.network_name}] Disconnecting... from {name}')
                #         self.disconnect(name)
                # except Exception:
                #     pass


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
        # print(f'Version ti!!c')
        return {
            "version": self.replica_state.version
        }
    
    def on_start_election(self):
        # print(f'[{self.network_name}] Acquire.')
        # self.ready_signal.hold()
        pass

    # def become_up_to_date(self):

    
    def on_become_leader(self):
        print("BECAME LEADER!!")
        print(f'[{self.network_name}] Release.')
        self.fast_forward.hold()

        # print(f'[{self.network_name}] outbounds {self.connection_map.get_outbound_names()}')

        versions = {}
        for peer in self.peer_names:
            
            if not self.has_connection(peer):
                for (a, b, c) in self.peer_addresses:
                    if a == peer:
                        try:
                            self.connect((b, c))
                        except Exception as e:
                            pass
            # print(f'Peer: {peer}, {self.has_connection(peer)}')

            if peer == self.network_name or not self.has_connection(peer):
                continue
            vers = self.send_message(peer, 'version', {})['version']
            versions[peer] = vers

        versions = list(versions.items())
        versions.sort(key=lambda x : x[1], reverse=True)

        if len(versions) > 0:
            name, top_version = versions[0]
            if self.replica_state.version < top_version:
                print(f'[{self.network_name}] Leader fast forwarded to more up-to-date replica {name}')
                self.__fast_forward_to_target(name)
        print(f'Versions: {versions}')
            # print(f'Peer: {peer}, Version: {vers}')
        self.fast_forward.ready()
        self.ready_signal.ready()

    def __fast_forward_to_target(
        self,
        target: str
    ):
        rs = self.send_message(target, "fast.forward", {}, timeout=2.0)
        self.replica_state.fast_forward(rs["__version"], rs["__state"])
        

    def on_elect_leader(self, leader, peer, target):
        # print(f'targ = {target}')
        # self.fast_forward.barrier()
        vers = self.send_message(target, 'version', {})['version']
        if vers > self.replica_state.version:
            print(f'[{self.network_name}] Requires a fast forward to version {vers}.')
            self.__fast_forward_to_target(target)
            
            # rs = self.send_message(target, "fast.forward", {}, timeout=2.0)
            # self.replica_state.fast_forward(rs["__version"], rs["__state"])
        print(f'[{self.network_name}] Release.')
        self.ready_signal.ready()
        # print(f'targ = {target}, version = {vers}')
        # return super().on_elect_leader(leader, peer, target

        # print(f'Elected leader: {leader}')

    # @node_handler(name='push.state_patch')
    # def handle_state_update(self, body: dict, sender: str):
    #     version = VersionedPatch.from_dict(body)
    #     self.replica_state.apply_update(version)

    #     self._print_state_hash()

    #     if self.replica_state.is_consistent():
    #         self.sync_event.set()
    #         self.ready = True
    #         self.ready_evt.set()

    #     return {"status": "success"}

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
        # print(f'Received _handle = {data}')
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
        # print(f'Receiving the regional heartbeat')
        if not self.node.is_leader():
            return {
                "status": "fail",
                "reason": f"not leader; current leader is {self.current_leader}"
            }

        # self.current_capital = self.network_name
        # self.current_leader = self.network_name
        # self.is_capital = True
        # self.is_leader = True

        # return self.__proxy_call(
        #     call=self.__handle_heartbeat,
        #     proxy_name='api.proxy.region.heartbeat',
        #     data=message,
        #     source=source
        # )

    @node_handler(name='api.proxy.state_update')
    def handle_operation_proxy(self, data):
        # print(f'Hnadle Op Proxy: {data}')
        state_name, _ = self.__handle_operation(data, None)
        return {"message": f"State {state_name} updated successfully."}

    @node_handler(name="api.update_state")
    def update_state(self, data):
        self.ready_signal.barrier()
        # print(f'Receiving update state...')
        if not self.node.is_leader():
            return {
                "status": "fail",
                "reason": f"not leader; current leader is {self.current_leader}"
            }
        # print(f'Updating state...')

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
        # while not self.ready:
            # self.ready_evt.wait()

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