from typing import Iterable, Optional, Callable
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
    unique_id: str
    priority: int

    @property
    def election_id(self) -> tuple[int, str]:
        return (self.priority, self.unique_id)


@dataclass
class BullyPacket:
    type: str
    destination: BullyPeer
    source: Optional[BullyPeer] = None


class HBMsgState(Enum):
    IDLE = 0
    WAIT = 1
    DEAD = 2


@dataclass
class HBState:
    state: HBMsgState
    last_hb: float


class BullyElectionHook(Enum):
    ON_ELECT_OTHER = 1
    ON_BECOME_LEADER = 2
    ON_ELECTION_START = 3


from ..state_machine import StateMachine, BaseStateMachine

class BullyElectionNode(BaseStateMachine):

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
        self.node_id = node.election_id
        self.verbose = verbose

        self.peer_list: list[BullyPeer] = list(peer_list)

        self.get_time = get_time


        self.outbox: list[BullyPacket] = []

        # The current leader.
        self.current_leader: Optional[tuple[int, str]] = None
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

    def _on_poll(self):
        return super()._on_poll()

    def get_state(self):
        return self.state
        # return super().get_state()



    def register_hook(
        self,
        hook: BullyElectionHook,
        functor: Callable[..., None]
    ):
        self.hooks[hook].append(functor)

    def __fire_hook(self, hook: BullyElectionHook):
        for fn in self.hooks[hook]:
            import threading
            threading.Thread(target=fn).start()

    def __reset_heartbeats(self):
        self.heartbeat: dict[BullyPeer, HBState] = {
            p: HBState(HBMsgState.IDLE, self.get_time())
            for p in self.peer_list
            if p.election_id != self.node_id
        }

    def poll(self):
        with self.bully_lock:
            outbox = self.outbox
            for o in outbox:
                o.source = self.node_info
            self.outbox = []
            return outbox

    def __peer_by_election_id(self, election_id: tuple[int, str]) -> Optional[BullyPeer]:
        if self.node_info.election_id == election_id:
            return self.node_info

        for p in self.peer_list:
            if p.election_id == election_id:
                return p
        return None

    def __leader_name(self) -> Optional[str]:
        if self.current_leader is None:
            return None
        peer = self.__peer_by_election_id(self.current_leader)
        return None if peer is None else peer.name

    def __end_election(self, leader_id: tuple[int, str]):
        old_leader = self.current_leader

        self.__set_leader(leader_id)
        self.election_in_progress = False

        if leader_id == self.node_id:
            self.__fire_hook(BullyElectionHook.ON_BECOME_LEADER)

        if old_leader != self.current_leader and leader_id != self.node_id:
            self.__fire_hook(BullyElectionHook.ON_ELECT_OTHER)

        self.__set_state(_BullyState.IDLE)

        leader_peer = self.__peer_by_election_id(leader_id)
        if leader_peer is not None:
            self.__print(
                f'[{self.node_info.name}] Elected node '
                f'{leader_peer.name} (priority={leader_peer.priority}, unique_id={leader_peer.unique_id}) as leader!'
            )
        else:
            self.__print(f'[{self.node_info.name}] Elected leader with key={leader_id}')

        self.__reset_heartbeats()

    def __higher_peers(self) -> list[BullyPeer]:
        return [p for p in self.peer_list if p.election_id > self.node_id]

    def __set_state(self, state: _BullyState):
        self.__print(f'[{self.node_info.name}] Switched to state: {state}')
        self.state = state
        self.last_state_change = self.get_time()

    def __start_election(self):
        with self.election_lock:
            if self.election_in_progress:
                return

            self.__print(f'[{self.node_info.name}] Starting an election.')
            self.election_in_progress = True

            for hook in self.hooks[BullyElectionHook.ON_ELECTION_START]:
                hook()

            higher_peers = self.__higher_peers()
            self.__print(f'[{self.node_info.name}] Peer list: {self.peer_list}')

            if len(higher_peers) == 0:
                self.outbox += [
                    BullyPacket('LEADER', peer)
                    for peer in self.peer_list
                    if peer.election_id != self.node_id
                ]
                self.__end_election(self.node_id)
            else:
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

    def __set_leader(self, leader_id: tuple[int, str]):
        self.current_leader = leader_id

    def __time_since_last_state_change(self):
        return self.get_time() - self.last_state_change

    def __handle_heartbeat_packet(self, packet: BullyPacket):
        assert packet.type == 'ACK'
        if self.current_leader is None or self.election_in_progress:
            return

        self.heartbeat[packet.source].state = HBMsgState.IDLE
        self.heartbeat[packet.source].last_hb = self.get_time()

    def get_leader_id(self) -> Optional[tuple[int, str]]:
        return self.current_leader
    
    # def get_leader
    

    def get_leader(self) -> Optional[BullyPeer]:
        if self.current_leader is None:
            return None
        return self.__peer_by_election_id(self.current_leader)

    def __manage_heartbeats(self):
        if self.current_leader is None or self.election_in_progress:
            return

        now = self.get_time()
        for node_info, state in self.heartbeat.items():
            should_send = (
                state.state == HBMsgState.IDLE
                and now - state.last_hb > self.hb_timeout / 5.0
            )

            if should_send:
                self.outbox.append(BullyPacket('HEARTBEAT', node_info))
                state.last_hb = now
                state.state = HBMsgState.WAIT
            elif state.state == HBMsgState.WAIT and (now - state.last_hb) > self.hb_timeout:
                if self.current_leader == node_info.election_id:
                    self.current_leader = None
                    self.election_in_progress = False
                    self.__set_state(_BullyState.IDLE)
                    self.__start_election()
                else:
                    state.state = HBMsgState.DEAD
                    self.__print(
                        f'[{self.node_info.name}] Detected non-leader node crash: '
                        f'{node_info.name} ({(now - state.last_hb):.2f}, timeout_threshold={self.hb_timeout})'
                    )

    def receive(self, packet: Optional[BullyPacket]):
        with self.bully_lock:
            return self.__receive(packet)

    def __receive(self, packet: Optional[BullyPacket]):
        if packet is not None:
            self.__print(f'[{self.node_info.name}] Receiving bully packet={packet} in state={self.state}')
        if (
            not (packet is not None and packet.type == 'BULLY')
            and self.state == _BullyState.WAIT_ELECTION
            and self.__time_since_last_state_change() > self.timeout
        ):
            self.__end_election(self.node_id)
            self.outbox += [
                BullyPacket('LEADER', peer)
                for peer in self.peer_list
                if peer.election_id != self.node_id
            ]

        if (
            not (packet is not None and packet.type == 'LEADER')
            and self.state == _BullyState.WAITING_FOR_LEADER
            and self.__time_since_last_state_change() > self.timeout
        ):
            self.__start_election()

        if packet is not None:
            if packet.type == 'LEADER':
                if (
                    self.current_leader == packet.source.election_id
                    and not self.election_in_progress
                    and self.state == _BullyState.IDLE
                ):
                    return

                self.__print(
                    f'[{self.node_info.name}] Elected leader: '
                    f'{packet.source.name} '
                    f'(priority={packet.source.priority}, unique_id={packet.source.unique_id})'
                )
                self.__end_election(packet.source.election_id)

            elif packet.type == 'ELECTION':
                if packet.source.election_id < self.node_id:
                    self.outbox.append(BullyPacket('BULLY', packet.source))

                    if self.current_leader == self.node_id and not self.election_in_progress:
                        self.outbox.append(BullyPacket('LEADER', packet.source))
                    elif not self.election_in_progress:
                        self.__start_election()

            elif packet.type == 'BULLY':
                if self.state == _BullyState.WAIT_ELECTION:
                    self.__set_state(_BullyState.WAITING_FOR_LEADER)
                    self.__print(f'[{self.node_info.name}] Current leader: {self.__leader_name()}')

            elif packet.type == 'HEARTBEAT':
                self.outbox.append(BullyPacket('ACK', packet.source))

            elif packet.type == 'ACK':
                self.__handle_heartbeat_packet(packet)

            else:
                raise RuntimeError(
                    f'Received a packet type: {packet.type}. '
                    f'Must be either LEADER or ELECTION.'
                )
        else:
            if self.current_leader is None and not self.election_in_progress:
                self.__start_election()

        self.__manage_heartbeats()

    def is_leader(self) -> bool:
        return self.current_leader == self.node_id