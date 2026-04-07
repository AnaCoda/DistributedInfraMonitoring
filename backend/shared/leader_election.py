import threading
import time
from typing import Dict, Optional, Iterable

from .node import node_handler

from ..common.leader_elec.bullynode import BullyElectionHook, BullyElectionNode, BullyPacket, BullyPeer

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

class BullyElectionMixin:
    """
    Reusable bully-election mixin.

    Assumptions:
    - The host class also inherits NodeBase
    - Peer node names follow a stable naming scheme like rm-1, rm-2, ...
    - Higher numeric ID wins
    """

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
        raise NotImplementedError("Have not implemented the on_start_election method.")

    def on_become_leader(self):
        raise NotImplementedError("Have not implemented the on_become_leader method.")

    def on_elect_leader(self, leader: int, peer: BullyPeer, target: str):
        raise NotImplementedError("Have not implemented the on_elect_leader method.")
    # def __try_fast_forward(self):
    #     for peer in self.peer_translator.keys():
    #         target = self.__translate_and_ensure_connect(peer)
    #         resp = self.send_message(target=target, method='api.who_is_leader', body={})
            
    #         print(f"CONNECTED YE {resp}")
        

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
            print(f'[{self.network_name}] Churned {message} (cost={time.time() - clocked:.2f}, error={e})')
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

    @node_handler(name='api.who_is_leader')
    def handle_who_is_leader(self, body: dict, source: str):
        return {
            "leader": f'rm-{self.node.get_leader_id()}',
            "is_leader": self.node.is_leader()
        }
    
    

    @node_handler(internal_ms=50)
    def poll_internal_node(self):
        self.wait_trigger("node_init")

        self.__recv_poll(None)
    
        # self.node_id = node_id
        # self.peer_names = list(peer_names)

        # self.is_leader = False
        # self.current_leader: Optional[str] = None

        # self.heartbeat_interval_ms = heartbeat_interval_ms
        # self.leader_timeout_ms = leader_timeout_ms

        

        # self.last_leader_heartbeat = time.time()

        # self.election_lock = threading.Lock()
        # self.election_in_progress = False
        # self.received_ok = False
        # self.awaiting_coordinator = False
        # self.coordinator_deadline: Optional[float] = None

    # def _peer_id_from_name(self, name: str) -> int:
    #     """
    #     Expects names like rm-3
    #     """
    #     try:
    #         return int(name.split("-")[-1])
    #     except Exception:
    #         return -1
        
    # def get_node_id(self):
    #     return int(self.network_name.split('-')[1])

    # def higher_peer_names(self):
    #     return [
    #         peer for peer in self.peer_names
    #         if self._peer_id_from_name(peer) > self.get_node_id()
    #     ]

    # def lower_peer_names(self):
    #     return [
    #         peer for peer in self.peer_names
    #         if self._peer_id_from_name(peer) < self.get_node_id()
    #     ]

    # def connected_peer_names(self):
    #     return [
    #         peer for peer in self.peer_names
    #         if self.has_connection(peer)
    #     ]

    # def start_election(self):
    #     with self.election_lock:
    #         if self.election_in_progress:
    #             return

    #         self.election_in_progress = True
    #         self.received_ok = False
    #         self.awaiting_coordinator = False
    #         self.coordinator_deadline = None

    #     print(f"[{self.network_name}] starting bully election")
    #     # print(f'[{self.higher_peer_names()}]')
    #     higher_alive = []
    #     for peer in self.higher_peer_names():
    #         if self.has_connection(peer):
    #             higher_alive.append(peer)
    #             try:
    #                 self.send_message_no_wait(
    #                     target=peer,
    #                     method="election.start",
    #                     body={
    #                         "candidate": self.network_name,
    #                         "candidate_id": self.get_node_id(),
    #                     },
    #                 )
    #             except Exception as e:
    #                 print(f"[{self.network_name}] failed to notify {peer} for election: {e}")

    #     print(f'[{self.network_name}] -> higher_alive = {higher_alive}')
    #     if not higher_alive:
    #         self.declare_leader()
    #         return

    #     with self.election_lock:
    #         self.awaiting_coordinator = True
    #         self.coordinator_deadline = time.time() + (self.leader_timeout_ms / 1000.0)

    # def declare_leader(self):
    #     with self.election_lock:
    #         self.is_leader = True
    #         self.current_leader = self.network_name
    #         self.election_in_progress = False
    #         self.received_ok = False
    #         self.awaiting_coordinator = False
    #         self.coordinator_deadline = None
    #         self.last_leader_heartbeat = time.time()

    #     print(f"[{self.network_name}] declaring self as leader")

    #     for peer in self.connected_peer_names():
    #         if peer == self.network_name:
    #             continue
    #         try:
    #             self.send_message_no_wait(
    #                 target=peer,
    #                 method="election.coordinator",
    #                 body={
    #                     "leader": self.network_name,
    #                     "leader_id": self.get_node_id(),
    #                 },
    #             )
    #         except Exception as e:
    #             print(f"[{self.network_name}] failed to announce coordinator to {peer}: {e}")

    #     # Hook for host class
    #     if hasattr(self, "on_become_leader"):
    #         self.on_become_leader()

    # def step_election(self):
    #     now = time.time()

        

    #     if self.is_leader:
    #         self.send_leader_heartbeat()
    #         return
        
       

    #     # If we have no peer connections yet, do nothing
    #     if len(self.connected_peer_names()) == 0:
    #         return
        
      
        
    #     if self.current_leader is None:
    #         self.start_election()
    #         return

    #     elapsed = now - self.last_leader_heartbeat
    #     if elapsed > (self.leader_timeout_ms / 1000.0):
    #         print(f"[{self.network_name}] leader timeout detected for {self.current_leader}")
    #         self.current_leader = None
    #         self.start_election()
    #         return

    #     with self.election_lock:
    #         deadline = self.coordinator_deadline
    #         waiting = self.awaiting_coordinator

    #     if waiting and deadline is not None and now > deadline:
    #         print(f"[{self.network_name}] coordinator wait timed out, restarting election")
    #         with self.election_lock:
    #             self.election_in_progress = False
    #             self.awaiting_coordinator = False
    #             self.received_ok = False
    #             self.coordinator_deadline = None
    #         self.start_election()

    # def send_leader_heartbeat(self):
    #     if not self.is_leader:
    #         return

    #     for peer in self.connected_peer_names():
    #         if peer == self.network_name:
    #             continue
    #         try:
    #             self.send_message_no_wait(
    #                 target=peer,
    #                 method="leader.heartbeat",
    #                 body={
    #                     "leader": self.network_name,
    #                     "leader_id": self.get_node_id(),
    #                     "ts": time.time(),
    #                 },
    #             )
    #         except Exception:
    #             pass

    # @node_handler(name="election.start")
    # def handle_election_start(self, body: dict, sender: str):
    #     """
    #     A lower-priority node is asking if a higher-priority node exists.
    #     We reply OK, then we start our own election if needed.
    #     """
    #     candidate = body.get("candidate")
    #     candidate_id = body.get("candidate_id")

    #     # Reply OK if we outrank them
    #     if self.get_node_id() > int(candidate_id):
    #         try:
    #             self.send_message_no_wait(
    #                 target=sender,
    #                 method="election.ok",
    #                 body={
    #                     "responder": self.network_name,
    #                     "responder_id": self.get_node_id(),
    #                 },
    #             )
    #         except Exception as e:
    #             print(f"[{self.network_name}] failed to send election.ok to {sender}: {e}")

    #         # Bully behavior: higher node should itself run election
    #         if not self.is_leader:
    #             self.start_election()

    #     return {"status": "ok"}

    # @node_handler(name="election.ok")
    # def handle_election_ok(self, body: dict, sender: str):
    #     with self.election_lock:
    #         # Ignore stale OKs if election already ended or a leader is already known
    #         if (not self.election_in_progress) or (self.current_leader is not None and not self.awaiting_coordinator):
    #             return {"status": "ignored"}

    #         self.received_ok = True
    #         self.awaiting_coordinator = True
    #         self.coordinator_deadline = time.time() + (self.leader_timeout_ms / 1000.0)

    #     print(f"[{self.network_name}] received OK from {sender}")
    #     return {"status": "ack"}

    # @node_handler(name="election.coordinator")
    # def handle_election_coordinator(self, body: dict, sender: str):
    #     leader = body.get("leader")
    #     leader_id = body.get("leader_id")

    #     with self.election_lock:
    #         self.is_leader = (leader == self.network_name)
    #         self.current_leader = leader
    #         self.last_leader_heartbeat = time.time()

    #         # Hard reset election state
    #         self.election_in_progress = False
    #         self.received_ok = False
    #         self.awaiting_coordinator = False
    #         self.coordinator_deadline = None

    #     print(f"[{self.network_name}] accepted coordinator {leader} (id={leader_id})")

    #     if hasattr(self, "on_new_leader"):
    #         self.on_new_leader(leader)

    #     return {"status": "ack"}

    # def on_new_leader(self, leader: str):
    #     print(f"[{self.network_name}] now following leader {leader}")


    # @node_handler(name="leader.heartbeat")
    # def handle_leader_heartbeat(self, body: dict, sender: str):
    #     leader = body.get("leader")

    #     if leader == sender:
    #         with self.election_lock:
    #             self.current_leader = leader
    #             self.last_leader_heartbeat = time.time()

    #             # If we are receiving leader heartbeats, we are not awaiting election resolution
    #             if leader != self.network_name:
    #                 self.is_leader = False
    #             self.election_in_progress = False
    #             self.awaiting_coordinator = False
    #             self.coordinator_deadline = None
    #             self.received_ok = False

    #     return {"status": "ack"}
    
    # def discover_current_leader(self):
    #     for peer in self.connected_peer_names():
    #         try:
    #             resp = self.send_message(peer, "api.who_is_leader", {}, timeout=1.0)
    #             leader = resp.get("leader")
    #             is_leader = resp.get("is_leader", False)

    #             if is_leader and leader == peer:
    #                 with self.election_lock:
    #                     self.current_leader = leader
    #                     self.is_leader = (leader == self.network_name)
    #                     self.last_leader_heartbeat = time.time()
    #                     self.election_in_progress = False
    #                     self.awaiting_coordinator = False
    #                     self.coordinator_deadline = None
    #                     self.received_ok = False
    #                 print(f"[{self.network_name}] discovered active leader {leader}")
    #                 return leader

    #             if leader and self.has_connection(leader):
    #                 with self.election_lock:
    #                     self.current_leader = leader
    #                     self.is_leader = (leader == self.network_name)
    #                     self.last_leader_heartbeat = time.time()
    #                     self.election_in_progress = False
    #                     self.awaiting_coordinator = False
    #                     self.coordinator_deadline = None
    #                     self.received_ok = False
    #                 print(f"[{self.network_name}] discovered leader {leader}")
    #                 return leader
    #         except Exception:
    #             continue

    #     return None