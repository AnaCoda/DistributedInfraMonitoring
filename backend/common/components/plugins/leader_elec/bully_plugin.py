import logging
import time

from colorama import Fore

from backend.common.components.events.event import NodeEvent
from backend.common.components.util import NetworkEntry

from ..plugin import Plugin

from typing import List, Optional

from .bully_state_machine import (
    BullyElectionHook,
    BullyElectionNode,
    BullyPacket,
    BullyPeer,
)
from ....layers.routing.routing_layer import node_handler


def _serialize_bully_peer(peer: BullyPeer) -> dict:
    return {
        "name": peer.name,
        "unique_id": peer.unique_id,
        "priority": peer.priority,
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

LOGGER = logging.getLogger("BULLY_PLUGIN")

class BullyPlugin(Plugin):

    def __init__(
        self,
        host,
        node: NetworkEntry,
        peers: List[NetworkEntry],
        heartbeat_interval_ms: int = 4000,
        leader_timeout_ms: int = 3000,
        verbose: bool = True
    ):
        super().__init__(host)
        self.init_bully_election(node, peers, heartbeat_interval_ms, leader_timeout_ms, verbose)

    
    def is_leader(self):
        return self.node.is_leader()
    
    def current_leader(self) -> Optional[str]:
        leader: Optional[BullyPeer] = self.node.get_leader()
        if leader is None:
            return None
        else:
            return leader.name
        # return self.node.get_leader().name
    



    def init_bully_election(
        self,
        node: NetworkEntry,
        peer_names: List[NetworkEntry],
        heartbeat_interval_ms: int = 4000,
        leader_timeout_ms: int = 3000,
        verbose: bool = True
    ):
        self.peer_map = { entry.name: entry for entry in peer_names }
        self.peers = peer_names

        node = BullyPeer(
            name=node.name,
            unique_id=int(node.name.split('-')[1]),
            priority=1
        )

        LOGGER.info(f'Initialized bully plugin with self={node} and peers={peer_names}')
        # print(f'INitialized bully elec w/ {node}, peer_names = {peer_names}')
        bully_peers  =[ BullyPeer(peer.name, int(peer.name.split('-')[1]), 1) for peer in peer_names ]
        self.node = BullyElectionNode(
            node=node.name,
            peer_list=[ peer.name for peer in peer_names ],
            hb_timeout=heartbeat_interval_ms / 1000.0,
            timeout=leader_timeout_ms / 1000.0,
            verbose=verbose
        )
        self.node.register_hook(BullyElectionHook.ON_ELECT_OTHER, self.__on_elect_other)
        self.node.register_hook(BullyElectionHook.ON_BECOME_LEADER, self.on_become_leader)
        self.node.register_hook(BullyElectionHook.ON_ELECTION_START, self.on_start_election)

        self.__bully_pause = True
        # print("INITTED")

    def __on_elect_other(self):
        # print(f'[{self.get_network_name()}] Hi! Another person has been elected. {self.node.get_leader_id()}')
        leader = self.node.get_leader()
        if leader is None:
            return

        try:
            target = self.__translate_and_ensure_connect(leader)
        except Exception as e:
            print(
                f"{Fore.RED}[BULLY][{self.get_network_name()}] "
                f"failed to prepare leader link "
                f"leader={leader.name} err={type(e).__name__}: {e}{Fore.RESET}"
            )
            return

        self.host.launch_background_thread(
            self.host.on_elect_leader,
            function_args=(self.node.get_leader_id(), leader, target)
        )

    def on_start_election(self):
        self.host.on_start_election()

    def on_become_leader(self):
        self.host.on_become_leader()

    def __translate_and_ensure_connect(self, destination: BullyPeer) -> Optional[str]:
        # target, ip, port = self.peer_translator[destination]
        entry = self.peer_map[destination.name]


        # for i in range(10):
        if entry.name == self.get_network_name():
            return entry.name
        

        self._try_connect(entry)
        

        # if not self.has_connection(entry.name):
        #     if not self._try_connect(entry):
        #         raise ConnectionError(f'Failed to connect to destination {entry.name}')
        #         # time.sleep(0.75)
        #         # continue
        #     # self.connect((ip, port))
        return entry.name
        # raise RuntimeError(f'Failed to ensure connection with target={target}')

    def __handle_bully_message(self, message: BullyPacket):
        # tries = 0
        # while not self.is_shutting_down():
            # tries += 1
            # if tries > 1:
            #     break
        try:
            if message.destination.name == self.get_network_name():
                return
            # print(f'Trying to send {message.destination.name}')
            if not self.has_connection(message.destination.name):
                # print(f'  BLOCKED!')
                return
            # print(f'Trying to send {message.destination.name}')
            target = self.__translate_and_ensure_connect(message.destination)
            if target is None:
                return
            self.send_message(
                target=target,
                method="handle.bully.msg",
                body=_serialize_bully_packet(message)
            )
            return
        except Exception as e:
            LOGGER.error(
                f"{Fore.RED}[{self.get_network_name()}] "
                f"send failed type={message.type} "
                f"dest={getattr(message.destination, 'name', 'unknown')} "
                f"err={type(e).__name__}: {e} (RETRYING){Fore.RESET}"
            )
            time.sleep(1.0)
            LOGGER.error("Failed to send a bully message.")
        # raise Exception(f'Failed to send a bully message {message}')
                
        

    def __handle_bully_messages(self, messages: list[BullyPacket]):
        for message in messages:
            self.host.launch_background_thread(
                self.__handle_bully_message,
                function_args=(message,)
            )

    @node_handler(name="handle.bully.msg")
    def handle_bully_msg(self, body: dict, sender: str):
        decoded = _deser_bully_packet(body)
        print(f'DECODED: {decoded}')
        self.__recv_poll(decoded)
        return {"status": "success"}

    def __recv_poll(self, message: Optional[BullyPacket]):
        self.node.receive(message)
        self.__handle_bully_messages(self.node.poll())


    @node_handler(name='bully.report.leader')
    def bully_report_leader(self, _):
        ids = self.node.get_leader_id()
        if ids is not None:
            ids = list(ids)
        return { 'leader': ids }
    

    # @node

    # @node_handler(event=NodeEvent.ON_CONNECT)
    # def on_connect_bully(self, name: str):
    #     while True:
    #         if self.node.get_leader_id() is None:
    #             # We do not currently have a leader.
    #             print(f'No current leader')
    #             if name in self.peer_map:
    #                 print(f'He')
    #                 peer = self.peer_map[name]

    #                 # Preallocate the connection/
    #                 self._try_connect(peer)

    #                 try:
    #                 # print(f'Sending request...')
    #                     check = self.send_message(peer.name, 'bully.report.leader', {}, timeout=5)
    #                     if check['leader'] is None:
    #                         self.__bully_pause = False
    #                 except Exception as e:
    #                     continue
                # print(f'Check: {check}')

            # print(f'CONNECTING LEADERLESS')

    @node_handler(internal_ms=300)
    def poll_bully_start(self):
        if self.node.get_leader_id() is not None:
            return
        output = []
        for peer in self.peers:
            try:
                ids = self.send_message(peer.name, 'bully.report.leader', {})['leader']
                output.append((peer, ids))
            except:
                pass
        if len(output) > 0:
            peer, leader = output[0]
            if leader is None:
                self.__bully_pause = False
            
        print(f'Output: {output}')


    @node_handler(event=NodeEvent.ON_DISCONNECT)
    def on_bully_disconnect(self, name: str):
        print("ON DISCONNECT")
        connected_to_cluster = False
        for peer in self.peers:
            if self.has_connection(peer.name):
                connected_to_cluster = True
                break
        if not connected_to_cluster:
            LOGGER.info("Node has been disconnected from the cluster.")
        # pass

    @node_handler(internal_ms=50)
    def poll_internal_node(self):
        if self.__bully_pause:
            return
        self.__recv_poll(None)