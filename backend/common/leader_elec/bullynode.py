from typing import Iterable, Optional, Union, Callable, Any
from threading import Lock
from dataclasses import dataclass
from time import time
from enum import Enum


class _BullyState(Enum):
    IDLE = 0
    WAIT_ELECTION = 1
    WAITING_FOR_LEADER = 2


@dataclass(frozen=True)
class BullyPeer:
    name: str
    id: int

@dataclass
class BullyPacket:
    type: str
    destination: BullyPeer
    source: Optional[BullyPeer] = None

class _HBMsgState(Enum):
    IDLE = 0
    WAIT = 1
    DEAD = 2

@dataclass
class _HBState:
    state: _HBMsgState
    last_hb: float

class BullyElectionHook(Enum):
    ON_ELECT_OTHER = 1
    ON_BECOME_LEADER = 2
    ON_ELECTION_START = 3

class BullyElectionNode:

    def __init__(
        self,
        node: BullyPeer,
        peer_list: Iterable[BullyPeer],
        timeout: float = 50.0,
        hb_timeout: float = 5.0,
        get_time: Callable[[], float] = time,
        verbose: bool = False
    ):
        # The ID of this node.
        self.node_info = node
        self.node_id = node.id
        self.verbose = verbose
        # List of peers.
        self.peer_list: list[BullyPeer] = list(peer_list)

        self.get_time = get_time


        self.outbox: list[BullyPacket] = []

        # The current leader.
        self.current_leader: Optional[int] = None

        self.state = _BullyState.IDLE

        self.hb_timeout = hb_timeout
        self.timeout = timeout


        self.last_state_change: Optional[float] = None

        # Election lock.
        self.election_lock = Lock()
        self.election_in_progress = False
        self.election_start_time: Optional[float] = None

        # Awaiting cooridnator.
        self.awaiting_coordinator = False

        # Heartbeat management dictionary.
        self.__reset_heartbeats()

        self.hooks = {
            BullyElectionHook.ON_ELECT_OTHER: [],
            BullyElectionHook.ON_BECOME_LEADER: [],
            BullyElectionHook.ON_ELECTION_START: []
        }

        self.bully_lock = Lock()

    def register_hook(
        self,
        hook: BullyElectionHook,
        functor: Callable[..., None]
    ):
        """
        Registers a hook that will be called on a specific event
        taking place.

        Args:
            hook (BullyElectionHook): The hook event we would like
            to subscribe to.
            functor (Callable[..., None]): The functor that will be
            called on the event.
        """
        self.hooks[hook].append(functor)
        
        
    def __reset_heartbeats(self):
        self.heartbeat: dict[int, Optional[_HBState]] = { p: _HBState(_HBMsgState.IDLE, self.get_time()) for p in self.peer_list if p.id != self.node_id }


    def poll(self):
        with self.bully_lock:
            outbox = self.outbox
            for o in outbox:
                o.source = self.node_info
            self.outbox = []
            return outbox
    
    def __end_election(self, j: int):
        old_leader = self.current_leader

        self.__set_leader(j)
        self.election_in_progress = False


        if j == self.node_id:
            for hook in self.hooks[BullyElectionHook.ON_BECOME_LEADER]:
                hook()
        if old_leader != self.current_leader:
            if j == self.node_id:
                pass
            else:
                for hook in self.hooks[BullyElectionHook.ON_ELECT_OTHER]:
                    hook()

        self.__set_state(_BullyState.IDLE)
        self.__print(f'[{self.node_info.name}] Elected node with ID={j} as leader!')
        self.__reset_heartbeats()

    def __higher_peers(self) -> list[BullyPeer]:
        return [ p for p in self.peer_list if p.id > self.node_id ]
    
    def __set_state(self, state: _BullyState):
        self.__print(f'[{self.node_info.name}] Switched to state: {state}')
        self.state = state
        self.last_state_change = self.get_time()

    def __start_election(self):
        with self.election_lock:
            if self.election_in_progress:
                return
            self.__print(f'[{self.node_info.name}] Starting an election.')
            # Start running the election.
            self.election_in_progress = True

            for hook in self.hooks[BullyElectionHook.ON_ELECTION_START]:
                hook()

            higher_peers = self.__higher_peers()
            self.__print(f'[{self.node_info.name}] Peer list: {self.peer_list}')
            if len(higher_peers) == 0:
                # We are the highest node.
                # RESULT: We announce ourself as leader to all
                # other nodes.
                self.outbox += [
                    BullyPacket('LEADER', peer)
                    for peer in self.peer_list if peer.id != self.node_id
                ]
                
                # We have won the election.
                self.__end_election(self.node_id)
            else:
                # We are not the highest node.
                # RESULT: Announce the election to all other nodes.
                self.election_start_time = self.get_time()
                self.__set_state(_BullyState.WAIT_ELECTION)
                self.outbox += [
                    BullyPacket('ELECTION', peer)
                    for peer in higher_peers
                ]
            
    def __print(self, msg: str):
        if self.verbose:
            import colorama
            print(f'{colorama.Fore.RED}[BULLY]{colorama.Fore.RESET} ', end='')
            print(msg)
            
    def __set_leader(self, id: int):
        """
        Sets the leader ID.
        
        Args:
            id (int): The leader ID.
        """
        self.current_leader = id

    def __time_since_last_state_change(self):
        return self.get_time() - self.last_state_change
    
    def __handle_heartbeat_packet(self, packet: BullyPacket):
        assert packet.type == 'ACK'
        if self.current_leader is None or self.election_in_progress:
            return
        # print(f'handling heartbeats for {self.node_info}')
        self.heartbeat[packet.source].state = _HBMsgState.IDLE
        self.heartbeat[packet.source].last_hb = self.get_time()

    def get_leader_id(self) -> Optional[int]:
        """
        Gets the leader ID if there is an elected leader.

        Returns:
            Optional[int]: The leader ID if present.
        """
        return self.current_leader

    def __manage_heartbeats(self):
        # If we do not have a leader or there is an election in progress,
        # the system is unstable and so we do not have to manage heartbeats.
        if self.current_leader is None or self.election_in_progress:
            return
        
        time = self.get_time()
        for node_info, state in self.heartbeat.items():
            should_send = state.state == _HBMsgState.IDLE and time - state.last_hb > self.hb_timeout / 3.0
            # print(f'Node {self.node_id} | id={node_info.id}, duration = {(time - state.last_hb)}')
            if should_send:
                # self.__print(f'[Node {self.node_info}] Earmarked packet for outbound hartbeat.')
                self.outbox.append(BullyPacket('HEARTBEAT', node_info))
                state.last_hb = time
                state.state = _HBMsgState.WAIT
            elif state.state == _HBMsgState.WAIT and (time - state.last_hb) > self.hb_timeout:
                if self.current_leader == node_info.id:
                    self.current_leader = None
                    self.election_in_progress = False
                    self.__set_state(_BullyState.IDLE)
                    self.__start_election()
                else:
                    state.state = _HBMsgState.DEAD
                    self.__print(f'[{self.node_info.name}] Detected non-leader node crash: {node_info.name} ({(time - state.last_hb):.2f})')
          

    def receive(self, packet: Optional[BullyPacket]):
        with self.bully_lock:
            return self.__receive(packet)
    def __receive(self, packet: Optional[BullyPacket]):
        
        
        if not (packet is not None and packet.type == 'BULLY') and self.state == _BullyState.WAIT_ELECTION and self.__time_since_last_state_change() > self.timeout:
            # In this case, we have not received a bully message from the other nodes.
            self.__end_election(self.node_id)
            # We send the leader message to all nodes i != j
            self.outbox += [
                BullyPacket('LEADER', peer)
                for peer in self.peer_list if peer.id != self.node_id
            ]

        if not (packet is not None and packet.type == 'LEADER') and self.state == _BullyState.WAITING_FOR_LEADER and self.__time_since_last_state_change() > self.timeout:
            # We were bullied, waiting for a leader packet.
            # We did not receive one.
            self.__start_election()

        
        


        if packet is not None:
            if packet.type == 'LEADER':
                # Set the leader to j.
                self.__print(f'[{self.node_info.name}] Elected leader: {packet.source.name} (id={packet.source.id})')
                j = packet.source.id
                self.__end_election(j)
                # self.__set_leader(j)
                # self.election_in_progress = False
                # self.__set_state(_BullyState.IDLE)
            elif packet.type == 'ELECTION':
                # print(f'[{self.node_info.name}] ')
                j: int = packet.source.id
                if j < self.node_id:
                    # If j < i
                    # Then we send a bully packet.
                    self.outbox.append(BullyPacket('BULLY', packet.source))
                    if not self.election_in_progress:
                        self.__start_election()
            elif packet.type == 'BULLY':
                # Wait for leader.
                if self.state == _BullyState.WAIT_ELECTION:
                    self.__set_state(_BullyState.WAITING_FOR_LEADER)
                    self.__print(f'[{self.node_info.name}] Current leader: {self.current_leader}')
            elif packet.type == 'HEARTBEAT':
                # print(f'[current={self.node_info.id}] Acknowleding heartbeat from {packet.source.id}')
                self.outbox.append(BullyPacket('ACK', packet.source))
            elif packet.type == 'ACK':
                
                self.__handle_heartbeat_packet(packet)
            else:
                raise RuntimeError(f'Received a packet type: {packet.type}. Must be either LEADER or ELECTION.')
        else:
            # If we received NO packet, and we do not have a leader AND there is no election!
            if self.current_leader is None and not self.election_in_progress:
                self.__start_election()

        # Manage heartbeats.
        self.__manage_heartbeats()

           

    def is_leader(self) -> bool:
        """
        Is this BullyElectionNode the leader?

        Returns:
            bool: if we are the leader
        """
        return self.current_leader == self.node_id
