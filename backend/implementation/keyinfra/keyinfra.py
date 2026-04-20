
from abc import abstractmethod
from hashlib import sha256
import time
from typing import Any, Callable, Dict, List, Tuple

from colorama import Fore, Style
from pydantic import BaseModel

from backend.common.components.events.connect import NodeConnectionType
from backend.common.components.plugins.leader_elec.bully_plugin import BullyPlugin
from backend.common.components.plugins.leader_elec.bully_state_machine import BullyPeer
from backend.common.components.plugins.replication.replication_plugin import ReplicationPlugin
from backend.common.components.storage.backend import StorageBackend
from backend.common.components.storage.disk import DiskBackend
from backend.common.components.storage.memory import MemoryStorageBackend
from backend.common.components.util import NetworkAddress, NetworkEntry
from backend.common.layers.routing.routing_layer import node_handler
from backend.common.raw import RawNode
from json import dumps

from backend.implementation.state.monitoring import ElectionState, HeartBeatState

class KeyInfraNode(RawNode):

    def __init__(
        self,
        entry: NetworkEntry,
        peers: List[NetworkEntry],
        operation_routes: List[Tuple[str, Callable[..., Any]]],
        backend: StorageBackend
    ):
        super().__init__(entry.name, entry.address.to_tuple())
        self.peers = [ peer for peer in peers if peer.name != self.get_network_name() ]

        self.leader_election = self.register_plugin(BullyPlugin(
            host=self,
            node=BullyPeer(self.get_network_name(), self.get_network_name(), 1),
            peers={
                BullyPeer(entry.name, entry.name, 1): (entry.name, entry.address.ip, entry.address.port)

                for entry in self.peers
            },
            heartbeat_interval_ms=8_000
        ))

        self.replication_plugin = self.register_plugin(ReplicationPlugin(
            host=self,
            name=self.get_network_name(),
            backend=backend,
            replicas=[ r.name for r in self.peers ],
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
        print(f'[{name}={Style.BRIGHT}{self.get_network_name()}{Style.RESET_ALL}] State = {Fore.LIGHTBLACK_EX}{self.get_state()}{Fore.RESET} {Fore.YELLOW}({digest[:4]}...){Fore.RESET} {Fore.GREEN}(version={self.replication_plugin.get_seq_num()}){Fore.RESET}')


    def get_state(self) -> BaseModel:
        return self.__state
    
    @node_handler(name='replication.version')
    def handle_replication_version(self, body):
        return { 'version': self.replication_plugin.get_seq_num() }
    
    
    def election_state(self):
        return ElectionState(
            name=self.get_network_name(),
            version=self.replication_plugin.get_seq_num(),
            leader=self.leader_election.current_leader(),
            heartbeat={
                bully.name: HeartBeatState(
                    heartbeat_state=state.state,
                    last_heartbeat=time.time() - state.last_hb
                )
                for bully, state in self.leader_election.node.heartbeat.items()
            }
        )
    
    @node_handler(name='ping.re')
    def handle_pingre(self, body: dict):
        return { 'name': self.get_network_name() }
    
    @node_handler(internal_ms=10_000)
    def pinger_int(self):
        for peer in self.peers:
            if peer.name == self.get_network_name():
                continue
            if not self.has_connection(peer.name):
                try:
                    self._try_connect(peer.address)
                except Exception:
                    pass
            if self.has_connection(peer.name):
                print(f'[PING] [{self.get_network_name()} -> {peer.name}] Starting ping...')
                try:
                    o = self.send_message(peer.name, 'ping.re', {})
                    print(f'[PING] [{self.get_network_name()} -> {peer.name}] Ping succeeded: {o}')
                except Exception as e:
                    print(
                        f'[PING] [{self.get_network_name()} -> {peer.name}] '
                        f'Ping failed: {type(e).__name__}: {e}'
                    )
    @node_handler(name='election.state')
    def handle_get_election_state(self, body: dict):
        print(f'GOT A GET ELECTION STATE CALL')
        return self.election_state().model_dump(mode='json')

    @node_handler(on_connect=NodeConnectionType.OUTBOUND)
    def handle_outbound_conn(self, name: str):
        print(f'{Fore.YELLOW}[CONNECTION]{Fore.RESET} Connected to {name} (type=OUTBOUND)')

    @node_handler(on_connect=NodeConnectionType.INBOUND)
    def handle_inbound_conn(self, name: str):
        print(f'{Fore.YELLOW}[CONNECTION]{Fore.RESET} Connected to {name} (type=INBOUND)')


    @node_handler(on_disconnect=NodeConnectionType.OUTBOUND)
    def handle_outbound_dconn(self, name: str):
        print(f'{Fore.YELLOW}[DISCONNECTION]{Fore.RESET} Disconnected from {name} (type=OUTBOUND)')

    @node_handler(on_disconnect=NodeConnectionType.INBOUND)
    def handle_inbound_dconn(self, name: str):
        print(f'{Fore.YELLOW}[DISCONNECTION]{Fore.RESET} Disconnected from {name} (type=INBOUND)')


    def __on_elect(
        self,
        target: str
    ):
        if target == self.get_network_name():
            version_dict = {}
            for peer in self.peers:
                if self.has_connection(peer.name):
                    try:
                        o = self.send_message(peer.name, 'replication.version', {})['version']
                        version_dict[peer.name] = o
                    except Exception:
                        pass
        print(f'ON ELECT PEER DICT: {version_dict}')


        self.replication_plugin.set_leader(target)


    def on_start_election(self):
        self.replication_plugin.set_leader(None)

    def on_become_leader(self):
        self.__on_elect(self.get_network_name())
        # self.replication_plugin.set_leader(self.get_network_name())

    def on_elect_leader(self, _l, _p, target):

        self.__on_elect(target)
        # self.replication_plugin.set_leader(target)
        
    @abstractmethod
    def _default_state(self) -> BaseModel:
        pass

    @abstractmethod
    def _parse_state(self, data: Dict) -> BaseModel:
        pass