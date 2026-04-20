from typing import Dict, List

from backend.common.components.storage.backend import StorageBackend
from backend.common.components.storage.memory import MemoryStorageBackend
from backend.common.components.util import NetworkEntry
from backend.common.layers.routing.routing_layer import node_handler
from backend.implementation.keyinfra.keyinfra import KeyInfraNode
from backend.implementation.state.monitoring import InfrastructureState, RegionState


class RegionalNode(KeyInfraNode):
    def __init__(
            self,
            region_name: str,
            entry: NetworkEntry,
            capital_addresses: List[NetworkEntry],
            peers: List[NetworkEntry],
            backend: StorageBackend = MemoryStorageBackend()
        ):
        self.region_name = region_name

        super().__init__(entry, peers, [
            ('infra.update', self.handle_infra_update)
        ], backend)

        
        self.capitals = capital_addresses

        self.__dirty = True

        # We are ready.
        self.ready_to_handle()
    
    def _default_state(self) -> RegionState:
        return RegionState(
            name=self.region_name,
            infrastructure={}
        )

    def _parse_state(self, data: Dict) -> RegionState:
        return RegionState.model_validate(data)
        # return super()._parse_state(data)
        # return super()._default_state()

    def handle_infra_update(self, body: dict):
        infra_state = InfrastructureState.model_validate(body)
        self.get_state().infrastructure[infra_state.name] = infra_state
        self.replication_plugin.commit(self.get_state())

        self._print_digest('region')
        self.__dirty = True

    
    def __send_update_target(
        self,
        target: str
    ):
        try:
            current_state: dict = self.get_state().model_dump()

            print(f'SENDING UPDATE')
            self.send_message(target, 'region.update', current_state)
            self.__dirty = False
        except Exception as e:
            print(f'[{self.get_network_name()}] Failed to send region update to target: {target} with exception={e}')

    @node_handler(internal_ms=500)
    def periodical(self):
        # Try to connect to the regions if we are
        # not already connected.
        for region in self.capitals:
            if not self.has_connection(region.name):
                self._try_connect(region.address)
        
        

        if self.__dirty:
            # Recall that we only need to send an
            # update to ONE of the nodes, not all of
            # them.
            for region in self.capitals:
                if self.has_connection(region.name):
                    self.__send_update_target(region.name)
                    break
