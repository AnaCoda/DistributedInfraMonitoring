from ...common.node.raw import RawNode
from ...common.node.layers.routing.routing_layer import node_handler
from ...common.node.common.plugins.leader_elec.bully_plugin import BullyPlugin
from ...common.node.common.plugins.heartbeat.capital_heartbeat_plugin import CapitalHeartbeatPlugin

from ...common.node.common.patching.mpatch import ManagedState
from ...common.node.common.plugins.leader_elec.bully_state_machine import BullyPeer

import threading
import datetime
import time
import hashlib
import json

from typing import Optional

from ...common.node.common.sync.signal import HoldSignal
from ...common.node.common.plugins.replication.replication_plugin import ReplicationPlugin

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


from ...common.node.common.storage.memory import MemoryStorageBackend

class CapitalNode(RawNode):
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

        self.replica_ready_signal = HoldSignal()
        self.fast_forward_signal = HoldSignal()

        self.bully_plugin = self.register_plugin(
            BullyPlugin(
                host=self,
                node=BullyPeer(
                    name=self.network_name,
                    unique_id=self._unique_id_from_name(self.network_name),
                    priority=self._priority_from_peer_count(),
                ),
                peers={
                    BullyPeer(
                        peer_name,
                        self._unique_id_from_name(peer_name),
                        self._priority_from_peer_count(),
                    ): (peer_name, peer_ip, peer_port)
                    for peer_name, peer_ip, peer_port in peer_addresses
                },
                verbose=False
            )
        )

        self.replication_plugin = self.register_plugin(ReplicationPlugin(
            host=self,
            name=self.get_network_name(),
            backend=MemoryStorageBackend(),
            replicas=self.peer_names,
            routes=[
                ('api.update_state', self.handle_test)
            ]
        ))

        # self.capital_heartbeat_plugin = self.register_plugin(
        #     CapitalHeartbeatPlugin(host=self)
        # )

        self.__internal_state = { 'state': {} }

        loaded: Optional[dict] = self.replication_plugin.load_state()
        if loaded is not None:
            print(f'[{self.network_name}] Restored state from snapshot.')
            self.__internal_state = loaded

        self.ready_to_handle()

    def handle_test(self, body: dict):
        name: str = body['name']
        data: str = body['state']

        self.__internal_state['state'][name] = data
        self.replication_plugin.commit(self.__internal_state)

        self._print_state_hash2()



    def _priority_from_peer_count(self) -> int:
        return len(self.peer_addresses)

    def _unique_id_from_name(self, name: str) -> str:
        return f"{name}-uid"

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
    
    def _print_state_hash2(self):
        serialized = json.dumps(
            obj=self.__internal_state,
            default=lambda x: str(x),
            sort_keys=True,
        )
        role = "leader" if self.is_leader else "follower"
        print(
            f"[{self.network_name} | {role}] version={self.replication_plugin.get_version_locked()}, "
            f"data={hashlib.sha256(serialized.encode()).hexdigest()}"
        )



    @node_handler(internal_ms=500)
    def maintain_peer_links(self):
        for peer_name, peer_ip, peer_port in self.peer_addresses:
            if peer_name == self.network_name:
                continue
            if self.has_connection(peer_name):
                continue
            try:
                self._net_connect((peer_ip, peer_port))
            except Exception:
                pass

    @node_handler(name="api.who_is_leader")
    def handle_who_is_leader(self, _body: dict, _source=None):
        return {
            "leader": self.bully_plugin.current_leader(),
            "is_leader": self.bully_plugin.is_leader(),
        }


    def on_start_election(self):
        pass

    def on_become_leader(self):
        print("BECAME LEADER!!")
        self.fast_forward_signal.hold()
        try:
            self.current_leader = self.network_name
            self.current_capital = self.network_name
            self.is_leader = True
            self.is_capital = True

            # We are now the leader.
            self.replication_plugin.set_leader(self.get_network_name())

        finally:
            self.fast_forward_signal.ready()
            self.replica_ready_signal.ready()


    def on_elect_leader(self, leader, peer, target):
        self.current_leader = target
        self.current_capital = target
        self.is_leader = (target == self.network_name)
        self.is_capital = self.is_leader

        self.replication_plugin.set_leader(target)

        self.replica_ready_signal.ready()


    def _national_infrastructure_snapshot(self) -> dict:
        self.replica_ready_signal.barrier()

        while not self.replica_state.is_consistent():
            self.sync_event.wait()

        return {
            "__version": self.replica_state.version,
            "__state": self.replica_state.inspect_dict(),
            "leader": self.current_leader,
            "capital": self.current_capital,
        }

    @node_handler(name="query.capital")
    def query_capital(self, _m):
        return self._national_infrastructure_snapshot()

    @node_handler(name="api.national_infrastructure")
    def get_national_status(self, _m):
        return self._national_infrastructure_snapshot()

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

    # @node_handler(internal_ms=1000)
    # def debug_leader_state(self):
    #     print(f"[{self.network_name}] leader={self.current_leader}, is_leader={self.is_leader}")