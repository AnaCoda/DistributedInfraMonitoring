from ....template import NodeTemplate
from .plugin import Plugin
from .....sync.signal import HoldSignal

from typing import Optional
import time
import threading

from ......common.leader_elec.bullynode import BullyElectionHook, BullyElectionNode, BullyPacket, BullyPeer
from ..routing import node_handler

def _serialize_bully_peer(peer: BullyPeer) -> dict:
    return {
        "id": peer.id,
        "name": peer.name
    }

def _deser_bully_peer(peer: dict) -> BullyPeer:
    return BullyPeer(**peer)

def _serialize_bully_packet(packet: BullyPacket) -> dict:
    return {
        "source": _serialize_bully_peer(packet.source),
        "destination": _serialize_bully_peer(packet.destination),
        "type": packet.type
    }

def _deser_bully_packet(packet: dict) -> BullyPacket:
    return BullyPacket(
        source=_deser_bully_peer(packet['source']),
        destination=_deser_bully_peer(packet['destination']),
        type=packet['type']
    )

class BullyPlugin(Plugin):
    
    def __init__(
        self,
        prefix: str,
        node: BullyPeer,
        peers: dict[BullyPeer, tuple[str, str, int]],
        heartbeat_interval_ms: int = 1500,
        leader_timeout_ms: int = 1500
    ):
        super().__init__()
        self.init_bully_election(node, peers, heartbeat_interval_ms, leader_timeout_ms)

    def init_bully_election(
        self,
        node: BullyPeer,
        peer_names: dict[BullyPeer, tuple[str, str, int]],
        heartbeat_interval_ms: int = 1500,
        leader_timeout_ms: int = 1500,
    ):
        self.peer_translator = peer_names
        print(f'INitialized bully elec w/ {node}, peer_names = {peer_names}')
        self.node = BullyElectionNode(
            node=node,
            peer_list=peer_names.keys(),
            hb_timeout=heartbeat_interval_ms / 1000.0,
            timeout=leader_timeout_ms / 1000.0,
            verbose=True
        )
        self.node.register_hook(BullyElectionHook.ON_ELECT_OTHER, self.__on_elect_other)
        self.node.register_hook(BullyElectionHook.ON_BECOME_LEADER, self.on_become_leader)
        self.node.register_hook(BullyElectionHook.ON_ELECTION_START, self.on_start_election)
        print("INITTED")
        self.set_trigger("node_init")


        # threading.Thread(target=self.__try_fast_forward).start()
        
    def __on_elect_other(self):
        print(f'[{self.network_name}] Hi! Another person has been elected. {self.node.get_leader_id()}')
        leader: int = self.node.get_leader_id()
            


        peer = next(filter(lambda x : x.id == leader, self.peer_translator.keys()))
        target = self.__translate_and_ensure_connect(peer)

        threading.Thread(target=self.on_elect_leader, args=(self.node.get_leader_id(), peer, target)).start()
        # self.on_elect_leader(self.node.get_leader_id(), peer, target)

    def on_start_election(self):
        pass

    def on_become_leader(self):
        pass

    def on_elect_leader(self, leader: int, peer: BullyPeer, target: str):
        pass



    def __translate_and_ensure_connect(self, destination: BullyPeer) -> str:
        target, ip, port = self.peer_translator[destination]

        if not self.has_connection(target):
            # print(f'Checking {target} -> {self.has_connection(target)}')
            self.connect((ip, port))
        return target

    def __handle_bully_message(self, message: BullyPacket):
        # print(f'[{self.network_name}] {message}')
        clocked = time.time()
        try:
            target = self.__translate_and_ensure_connect(message.destination)
            # print(f'[{self.network_name}] sending to {target} {message}')
            self.send_message_no_wait(target=target, method="handle.bully.msg", body=_serialize_bully_packet(message))
        except Exception as e:
            # print(f'[{self.network_name}] Churned {message} (cost={time.time() - clocked:.2f}, error={e})')
            # Connection churn is expected during elections/re-registers.
            # Drop this packet and rely on the next poll/heartbeat.
            pass
        # print(f'Peer ({message.destination}) -> {self.target}')
        # self.__recv_poll(message)


    def __handle_bully_messages(self, messages: list[BullyPacket]):
        for message in messages:
            threading.Thread(target=self.__handle_bully_message, args=(message,)).start()
            # self.__handle_bully_message(message)

    @node_handler(name="handle.bully.msg")
    def handle_bully_msg(self, body: dict, sender: str):
        self.wait_trigger("node_init")
        decoded = _deser_bully_packet(body)
        # print(f'RECEIVING BULLY: {decoded}')
        self.__recv_poll(decoded)
        # self.__handle_bully_message(decoded)

    def __recv_poll(self, message: Optional[BullyPacket]):
        self.node.receive(message)
        self.__handle_bully_messages(self.node.poll())

    def __get_peer_by_id(self, id: int) -> Optional[BullyPeer]:
        for item in self.peer_translator.keys():
            if item.id == id:
                return item
        return None

    @node_handler(name='api.who_is_leader')
    def handle_who_is_leader(self, body: dict, source: str):
        return {
            "leader": self.__get_peer_by_id(self.node.get_leader_id()),
            "is_leader": self.node.is_leader()
        }
    
    

    @node_handler(internal_ms=50)
    def poll_internal_node(self):
        self.wait_trigger("node_init")

        self.__recv_poll(None)

