import logging
from threading import Lock
import time

from colorama import Fore
from pydantic import BaseModel
from pydantic.types import T

from backend.common.components.events.event import NodeEvent
from backend.common.components.util import NetworkEntry

from ..plugin import Plugin

from typing import Dict, List, Optional, Tuple

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

LOGGER = logging.getLogger("plugin::bully")


class ElectionState(BaseModel):
    updating_states: bool
    election_in_progress: bool
    current_leader: Optional[BullyPeer]
    received_ok: bool 


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

        # This prevents a race condition.
        self.__on_connect_lock = Lock()
        self.__start_election_lock = Lock()


    
    def is_leader(self):
        current = self.current_leader()
        return current is not None and current == self.get_network_name()
        # return self.node.is_leader()
    
    def current_leader(self) -> Optional[str]:
        with self.bully_lock:
            if self.bully_state.current_leader is None:
                return None
            else:
                return self.bully_state.current_leader.name
    

    # def __current_leader_peer(
        # self
    # ) -> Optional[BullyPeer]:
        # return self.node.get_leader().name
    



    def init_bully_election(
        self,
        node: NetworkEntry,
        peer_names: List[NetworkEntry],
        heartbeat_interval_ms: int = 4000,
        leader_timeout_ms: int = 3000,
        verbose: bool = True
    ):
        all_names: List[str] = list(set([ node.name ] + [ p.name for p in peer_names ]))
        all_names.sort()
        all_names: List[Tuple[int, str]] = list(enumerate(all_names))

        self.node_map: Dict[str, BullyPeer] = {
            name: BullyPeer(name=name, unique_id=id, priority=0) for id, name in all_names
        }
        self.peer_names =  [ p for p in self.node_map if p != self.get_network_name() ]

        self.peer_map = { entry.name: entry for entry in peer_names }
        self.peers = peer_names


        LOGGER.info(f'Initialized bully plugin with self={node} and peers={peer_names}')
        
        #########
        # BULLY STATE
        #########
        self.bully_lock = Lock()
        self.bully_state = ElectionState(
            updating_states=True,
            election_in_progress=False,
            current_leader=None,
            received_ok=False
        )
        
        # # print(f'INitialized bully elec w/ {node}, peer_names = {peer_names}')
        # # bully_peers  =[ BullyPeer(peer.name, int(peer.name.split('-')[1]), 1) for peer in peer_names ]
        # self.node = BullyElectionNode(
        #     node=node.name,
        #     peer_list=[ peer.name for peer in peer_names ],
        #     hb_timeout=heartbeat_interval_ms / 1000.0,
        #     timeout=leader_timeout_ms / 1000.0,
        #     verbose=verbose
        # )
        # self.node.register_hook(BullyElectionHook.ON_ELECT_OTHER, self.__on_elect_other)
        # self.node.register_hook(BullyElectionHook.ON_BECOME_LEADER, self.on_become_leader)
        # self.node.register_hook(BullyElectionHook.ON_ELECTION_START, self.on_start_election)

        # self.__bully_pause = True
        # print("INITTED")

    def set_own_priority(self, priority: int):
        with self.bully_lock:
            if self.node_map[self.get_network_name()].priority != priority:
                LOGGER.info(f'Updating BULLY priority to priority={priority}')
            self.node_map[self.get_network_name()].priority = priority
            
         

    def __set_priority(
        self,
        peer: BullyPeer
    ):
        if self.node_map[peer.name].priority != peer.priority:
            LOGGER.info(f'Updating name={peer.name} priority to priority={peer.priority}')
        self.node_map[peer.name] = peer

    @node_handler(name='bully.inquire')
    def bully_inquire(self, body: dict):
        peer = BullyPeer.model_validate(body)

        with self.bully_lock:
            self.__set_priority(peer)
            current_leader = self.bully_state.current_leader

        return { 'node': self.node_map[self.get_network_name()].model_dump(mode='json'), 'leader': current_leader.model_dump(mode='json') if current_leader is not None else current_leader }

    def __try_reach_out(
        self
    ) -> Dict[str, Optional[BullyPeer]]:
        output = []
        for peer in self.peer_names:
            try:
                ids = self.send_message(peer, 'bully.inquire', self.node_map[self.get_network_name()].model_dump(mode='json'))

                # Update our local information about that node.
                node = BullyPeer.model_validate(ids['node'])
                with self.bully_lock:
                    self.__set_priority(node)

                output.append(BullyPeer.model_validate(ids['leader']) if ids['leader'] is not None else None)
            except Exception as e:
                # print(f'E: {e}')
                pass
        return output
        # print(f'Output: {output}')

    @node_handler(internal_ms=100)
    def bully_loop(self):
        with self.bully_lock:
            cur_leader = self.bully_state.current_leader
        if cur_leader is None:
            self.__start_election()
        elif cur_leader.name != self.get_network_name() and not self.has_connection(cur_leader.name):
            print("HEYYE")
            self.__on_detect_leader_down(cur_leader.name)
        # else:

    def __on_detect_leader_down(self, name: str):
        with self.bully_lock:
            if self.bully_state.current_leader is not None and self.bully_state.current_leader.name == name:
                logging.info("The leader has disconnected.")
                self.bully_state.current_leader = None
                should_elect = True
            else:
                should_elect = False

        if should_elect:
            self.__start_election()

    @node_handler(event=NodeEvent.ON_DISCONNECT)
    def on_peer_disconnect(self, name: str):
        logging.info(f'Detected discnnect from {name}')
        with self.bully_lock:
            if self.bully_state.current_leader is not None and self.bully_state.current_leader.name == name:
                logging.info("The leader has disconnected.")
                self.bully_state.current_leader = None
                should_elect = True
            else:
                should_elect = False

        if should_elect:
            self.__start_election()

    @node_handler(event=NodeEvent.ON_CONNECT)
    def on_peer_connect(self, name: str):
        try:
            ids = self.send_message(name, 'bully.inquire', self.node_map[self.get_network_name()].model_dump(mode='json'))

            # Update our local information about that node.
            node = BullyPeer.model_validate(ids['node'])
            with self.bully_lock:
                self.__set_priority(node)

            # output.append(BullyPeer.model_validate(ids['leader']) if ids['leader'] is not None else None)
        except Exception as e:
            # print(f'E: {e}')
            pass
    # @node_handler(event=NodeEvent.ON_CONNECT)
    # def on_peer_connect(self, name: str):
    #     with self.__on_connect_lock:
            
    #         with self.bully_lock:
    #             if not self.bully_state.updating_states:
    #                 # This basically prevents two of these running concurrently,
    #                 # which could happen in older versions when two connection events
    #                 # would fire.
    #                 return
    #             if name in self.node_map and self.get_network_name() != name:
    #                 LOGGER.info("Connected to another peer node.")
                
    #         # Now we need to collect information on other nodes.
    #         while True:
    #             detection = self.__try_reach_out()
    #             if len(detection) > 0:
    #                 # We have collected information from peers on who the leader is.
    #                 LOGGER.info(f'Detected leader election information from {len(detection)} node(s).')
                    
    #                 should_start_election = False
    #                 if any(x is None for x in detection):
    #                     should_start_election = True
    #                 else:
    #                     detection.sort(key=lambda x : x.election_id, reverse=True)
    #                     if detection[0].election_id < self.node_map[self.get_network_name()].election_id:
    #                         should_start_election = True
    #                     else:
    #                         # There is already a leader, so we just absorb this leader.
    #                         with self.bully_lock:
    #                             self.bully_state.current_leader = detection[0]
    #                             self.bully_state.updating_states = False
                        
    #                 if should_start_election:
    #                     # We should start an election.
    #                     with self.bully_lock:
    #                         self.bully_state.updating_states = False
    #                     self.__start_election()
                    
    #                 # We are done here.
    #                 break


                
        
    #################
    # BULLY METHODS #
    ##################
    def __higher_peers(
        self
    ) -> List[BullyPeer]:
        
        return [ peer for peer_name, peer in self.node_map.items()
                    if peer_name != self.get_network_name()
                    and self.__lookup_node(self.get_network_name()).election_id < peer.election_id
        ]
    
    def __internal_state(
        self
    ) -> dict:
        return self.node_map[self.get_network_name()].model_dump(mode='json')

    def __lookup_node(
        self,
        name: str
    ) -> BullyPeer:
        return self.node_map[name]
    
    @node_handler(name='bully.leader')
    def bully_leader(self, body: dict):
        leader = BullyPeer.model_validate(body['peer'])

        with self.bully_lock:
            self.__set_priority(leader)

            if leader.election_id < self.node_map[self.get_network_name()].election_id:
                should_challenge = True
            else:
                should_challenge = False
                self.bully_state.current_leader = leader
                self.bully_state.election_in_progress = False
                self.bully_state.received_ok = False
                self.bully_state.updating_states = False

        if should_challenge:
            self.launch_background_thread(self.__start_election, None)

        if leader.name == self.get_network_name():
            self.on_become_leader()
        else:
            self.on_elect_other(leader.name)
        # print(f'got bully.leader @ {leader}')

    @node_handler(name='bully.election')
    def bully_election(self, body: dict):
        peer = BullyPeer.model_validate(body['peer'])
        print(f'GOT ELECTION MESSAGE.')

        with self.bully_lock:
            self.__set_priority(peer)
            me = self.node_map[self.get_network_name()]

        if me.election_id > peer.election_id:
            try:
                self.send_message_no_wait(peer.name, 'bully.ok', { 'peer': self.__internal_state() })
            except:
                pass
        
            self.launch_background_thread(self.__start_election, None)
        
    @node_handler(name='bully.ok')
    def bully_ok(self, body: dict):
        print(f'GOT BULLY OK')
        peer = BullyPeer.model_validate(body['peer'])
        
        with self.bully_lock:
            # Update the node priority and notify that we received OK.
            self.__set_priority(peer)
            if self.bully_state.election_in_progress:
                self.bully_state.received_ok = True


    def __declare_self_leader(
        self
    ):
        with self.bully_lock:
            me = self.node_map[self.get_network_name()]
            self.bully_state.current_leader = me
            self.bully_state.election_in_progress = False
            self.bully_state.received_ok = False
            self.bully_state.updating_states = False
        
        for peer in self.peer_names:
            try:
                self.send_message_no_wait(peer, 'bully.leader', { 'peer': me.model_dump(mode='json') })
            except:
                pass

        # Call the on_become_leader method
        # where we can do some cleaner separated
        # logic.
        self.on_become_leader()


    # @node_handler(inter)
        
    def __start_election(
        self
    ):

        with self.bully_lock:
            if self.bully_state.election_in_progress:
                # We do not want two elections running concurrently.
                return
            LOGGER.info('Starting an election.')
            
            # Mark that there is an election in progress.
            self.bully_state.election_in_progress = True
            self.bully_state.received_ok = False
            self.bully_state.current_leader = None

            # Higher peers.
            higher = self.__higher_peers()
        if len(higher) == 0:
            LOGGER.info('There are no higher peers.')
            # Case 1: There are no higher peers.
            # for peer in self.peer_names:
            #     self.send_message(peer, 'bully.leader', { 'peer': self.__internal_state() })
            # self.on_become_leader()
            self.__declare_self_leader()
            return
        else:
            LOGGER.info('There exist higher peers.')
            for peer in higher:
                try:
                    self.send_message_no_wait(peer.name, 'bully.election', { 'peer': self.__internal_state() })
                except:
                    pass
            
            # Wait two seconds.
            start = time.time()
            while time.time() - start < 2.5:
                with self.bully_lock:
                    # Check if we have received an OK, if
                    # we have we can break out.
                    if self.bully_state.received_ok:
                        break
                time.sleep(0.25)

            with self.bully_lock:
                got_ok = self.bully_state.received_ok
                leader = self.bully_state.current_leader
            
            if leader is not None:
                return

            if not got_ok:
                self.__declare_self_leader()

            # print(f'ELAPSED!!!!!!!!')

                # print(f'HIGHER: {peer.name}')

    # def __on_elect_other(self):
    #     # print(f'[{self.get_network_name()}] Hi! Another person has been elected. {self.node.get_leader_id()}')
    #     leader = self.node.get_leader()
    #     if leader is None:
    #         return

    #     try:
    #         target = self.__translate_and_ensure_connect(leader)
    #     except Exception as e:
    #         print(
    #             f"{Fore.RED}[BULLY][{self.get_network_name()}] "
    #             f"failed to prepare leader link "
    #             f"leader={leader.name} err={type(e).__name__}: {e}{Fore.RESET}"
    #         )
    #         return

    #     self.host.launch_background_thread(
    #         self.host.on_elect_leader,
    #         function_args=(self.node.get_leader_id(), leader, target)
    #     )

 

    def on_start_election(self):
        self.host.on_start_election()

    def on_become_leader(self):
        # with self.bully_lock:
            # self.bully_state.current_leader = self.node_map[self.get_network_name()]
        LOGGER.info(f'We have become the leader.')
        self.host.on_become_leader()
    
    def on_elect_other(self, leader: str):
        LOGGER.info(f'We have elected node={leader}')
        self.host.on_elect_other(leader)

