import time
import random
import threading
import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.common.node.common.util import NetworkEntry
from backend.implementation.keyinfra.keyinfra import KeyInfraNode

from ...common.node.raw import RawNode
from ...common.node.layers.routing.routing_layer import node_handler
from ...common.node.common.plugins.heartbeat.regional_heartbeat_plugin import RegionalHeartbeatPlugin
from ...common.node.common.plugins.heartbeat.regional_leader_plugin import RegionalLeaderPlugin
from ...common.node.common.events.connect import NodeConnectionType
from ...common.node.common.sync.mdns import DnsEntry
from ...common.node.common.plugins.leader_elec.bully_state_machine import BullyPeer
from ...common.node.common.patching.mpatch import ManagedState


from ...common.node.common.plugins.leader_elec.bully_plugin import BullyPlugin
from ...common.node.common.plugins.replication.replication_plugin import ReplicationPlugin
from ...common.node.common.storage.memory import MemoryStorageBackend

# def _source_manager() -> ManagedState:
#     return ManagedState.from_dict(1, {
#         "region_state": {
#             "name": None,
#             "state": {},
#             "meta": {},
#         }
#     })
from ..state.monitoring import InfrastructureState, RegionState, StateInfrastructure


class RegionalNode(KeyInfraNode):
    def __init__(
            self,
            entry: NetworkEntry,
            capital_addresses: List[NetworkEntry],
            peers: List[NetworkEntry]
        ):
        super().__init__(entry, peers, [
            ('infra.update', self.handle_infra_update)
        ])

        # We are ready.
        self.ready_to_handle()
    
    def _default_state(self) -> RegionState:
        return RegionState(
            name=self.get_network_name(),
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

        print(f'[region={self.get_network_name()}] Resulting state after update: {self.get_state()}')

    # def __init__(
    #     self,
    #     region_name: str,
    #     address: Tuple[str, int],
    #     capital_candidates: List[NetworkEntry],
    #     interval_ms: int = 2000,
    #     network_name: Optional[str] = None,
    #     replica_peer_addresses: List[NetworkEntry] = None,
    # ):
    #     super().__init__(network_name, address)


    #     self.capital_candidates = capital_candidates

    #     # print(f'REPLICA PEER ADDRESSES: {replica_peer_addresses}')
    #     self.leader_election = self.register_plugin(BullyPlugin(
    #         host=self,
    #         node=BullyPeer(self.get_network_name(), self.get_network_name(), 1),
    #         peers={
    #             BullyPeer(entry.name, entry.name, 1): (entry.name, entry.address.ip, entry.address.port)

    #             for entry in replica_peer_addresses
    #         }
    #     ))

    #     self.replication_plugin = self.register_plugin(ReplicationPlugin(
    #         host=self,
    #         name=self.get_network_name(),
    #         backend=MemoryStorageBackend(),
    #         replicas=[ r.name for r in replica_peer_addresses ],
    #         routes=[
    #             ('infra.update', self.handle_infra_update)
    #         ]
    #     ))

    #     # self.leader_election.


    #     # self.__state = StateInfrastructure()
    #     self.__state = RegionState(
    #         name=self.get_network_name(),
    #         infrastructure={}
    #     )

    #     loaded = self.replication_plugin.load_state()
    #     if loaded is not None:
    #         self.__state = RegionState.model_validate(loaded)

    #     self.__dirty = True

    #     # Mark regional node as ready to start handling incoming
    #     # messages.
    #     self.ready_to_handle()

    # def handle_infra_update(self, body: dict):
    #     infra_state = InfrastructureState.model_validate(body)
    #     self.__state.infrastructure[infra_state.name] = infra_state
    #     self.replication_plugin.commit(self.__state)

    #     print(f'[region={self.get_network_name()}] Resulting state after update: {self.__state}')


    # # @node_handler(internal_ms=400)
    # # def region_routine(self):
    #     # f

  

    # def on_start_election(self):
    #     pass

    # def on_become_leader(self):
    #     self.replication_plugin.set_leader(self.get_network_name())

    # def on_elect_leader(self, leader, peer, target):
    #     self.replication_plugin.set_leader(target)

    # def shutdown(self):
    #     super().shutdown()
   
