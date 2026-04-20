from typing import List

from backend.common.components.storage.backend import StorageBackend
from backend.common.components.storage.memory import MemoryStorageBackend
from backend.common.components.util import NetworkEntry
from backend.common.layers.routing.routing_layer import node_handler
from backend.implementation.keyinfra.keyinfra import KeyInfraNode
from backend.implementation.state.monitoring import CapitalState, RegionState




class CapitalNode(KeyInfraNode):

    def __init__(
        self,
        capital_name: str,
        entry: NetworkEntry,
        peers: List[NetworkEntry],
        backend: StorageBackend = MemoryStorageBackend()
    ):
        self.capital_name = capital_name
        super().__init__(entry, peers, [
            ('region.update', self.region_update),
            ('query.capital', self.query_capital)
        ], backend)

        # We are ready.
        self.ready_to_handle()

    def region_update(self, body: dict):
        update = RegionState.model_validate(body)


        # Update that state and then commit it.
        self.get_state().regions[update.name] = update
        self.replication_plugin.commit(self.get_state())

        self._print_digest('capital')

    # @node_handler(name='query.capital')
    def query_capital(self, body: dict, source: str):
        # pass
        return self.get_state().model_dump()

    @node_handler(name='query.capital.local')
    def query_capital_local(self, body, source):
        return self.get_state().model_dump()

    def _default_state(self) -> CapitalState:
        return CapitalState(
            name=self.capital_name,
            regions={}
        )
    
    def _parse_state(self, data):
        return CapitalState.model_validate(data)
       
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
