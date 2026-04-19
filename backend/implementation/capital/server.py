from typing import List

from backend.common.components.util import NetworkEntry
from backend.implementation.keyinfra.keyinfra import KeyInfraNode
from backend.implementation.state.monitoring import CapitalState, RegionState




class CapitalNode(KeyInfraNode):

    def __init__(
        self,
        capital_name: str,
        entry: NetworkEntry,
        peers: List[NetworkEntry]
    ):
        self.capital_name = capital_name
        super().__init__(entry, peers, [
            ('region.update', self.region_update)
        ])

        # We are ready.
        self.ready_to_handle()

    def region_update(self, body: dict):
        update = RegionState.model_validate(body)


        # Update that state and then commit it.
        self.get_state().regions[update.name] = update
        self.replication_plugin.commit(self.get_state())

        self._print_digest('capital')


    def _default_state(self) -> CapitalState:
        return CapitalState(
            name=self.capital_name,
            regions={}
        )
    
    def _parse_state(self, data):
        return CapitalState.model_validate(data)
       