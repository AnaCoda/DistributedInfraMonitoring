
from abc import abstractmethod
from hashlib import sha256
from typing import Any, Callable, Dict, List, Tuple

from colorama import Fore, Style
from pydantic import BaseModel

from backend.common.node.common.plugins.leader_elec.bully_plugin import BullyPlugin
from backend.common.node.common.plugins.leader_elec.bully_state_machine import BullyPeer
from backend.common.node.common.plugins.replication.replication_plugin import ReplicationPlugin
from backend.common.node.common.storage.memory import MemoryStorageBackend
from backend.common.node.common.util import NetworkEntry
from backend.common.node.raw import RawNode
from json import dumps

class KeyInfraNode(RawNode):

    def __init__(
        self,
        entry: NetworkEntry,
        peers: List[NetworkEntry],
        operation_routes: List[Tuple[str, Callable[..., Any]]]
    ):
        super().__init__(entry.name, entry.address.to_tuple())
        self.peers = peers

        self.leader_election = self.register_plugin(BullyPlugin(
            host=self,
            node=BullyPeer(self.get_network_name(), self.get_network_name(), 1),
            peers={
                BullyPeer(entry.name, entry.name, 1): (entry.name, entry.address.ip, entry.address.port)

                for entry in peers
            }
        ))

        self.replication_plugin = self.register_plugin(ReplicationPlugin(
            host=self,
            name=self.get_network_name(),
            backend=MemoryStorageBackend(),
            replicas=[ r.name for r in peers ],
            routes=operation_routes
        ))

        self.__state = self._default_state()
        loaded = self.replication_plugin.load_state()
        if loaded is not None:
            self.__state = self._parse_state(loaded)

    def _print_digest(
        self,
        name: str
    ):
        state_dump: Dict = self.get_state().model_dump(mode='json')

        digest = sha256(dumps(state_dump, sort_keys=True).encode()).hexdigest()
        print(f'[{name}={Style.BRIGHT}{self.get_network_name()}{Style.RESET_ALL}] State = {Fore.LIGHTBLACK_EX}{self.get_state()}{Fore.RESET} {Fore.YELLOW}({digest[:4]}...){Fore.RESET}')


    def get_state(self) -> BaseModel:
        return self.__state
    


    def on_start_election(self):
        pass

    def on_become_leader(self):
        self.replication_plugin.set_leader(self.get_network_name())

    def on_elect_leader(self, _l, _p, target):
        self.replication_plugin.set_leader(target)
        
    @abstractmethod
    def _default_state(self) -> BaseModel:
        pass

    @abstractmethod
    def _parse_state(self, data: Dict) -> BaseModel:
        pass