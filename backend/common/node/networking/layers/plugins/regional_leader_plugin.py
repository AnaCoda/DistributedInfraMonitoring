from .plugin import Plugin

from ......common.leader_elec.bullynode import (
    BullyElectionHook,
    BullyElectionNode,
    BullyPacket,
    BullyPeer,
)
from ..routing import node_handler


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
        "type": packet.type,
    }


def _deser_bully_packet(packet: dict) -> BullyPacket:
    return BullyPacket(
        source=_deser_bully_peer(packet["source"]),
        destination=_deser_bully_peer(packet["destination"]),
        type=packet["type"],
    )


class RegionalLeaderPlugin(Plugin):
    def __init__(
        self,
        host,
        node: BullyPeer,
        peers: dict[BullyPeer, tuple[str, str, int]],
        heartbeat_interval_ms: int = 1500,
        leader_timeout_ms: int = 1500,
    ):
        super().__init__(host)
        self.peer_translator = peers
        self.node = BullyElectionNode(
            node=node,
            peer_list=peers.keys(),
            hb_timeout=heartbeat_interval_ms / 1000.0,
            timeout=leader_timeout_ms / 1000.0,
            verbose=True,
        )
        self.node.register_hook(BullyElectionHook.ON_ELECT_OTHER, self.__on_elect_other)
        self.node.register_hook(BullyElectionHook.ON_BECOME_LEADER, self.on_become_leader)
        self.node.register_hook(BullyElectionHook.ON_ELECTION_START, self.on_start_election)

    def __on_elect_other(self):
        leader = self.node.get_leader()
        if leader is None:
            return

        target = self.__translate_and_ensure_connect(leader)
        self.host.launch_background_thread(
            self.host.on_elect_region_leader,
            function_args=(self.node.get_leader_id(), leader, target),
        )

    def on_start_election(self):
        self.host.on_start_region_election()

    def on_become_leader(self):
        self.host.on_become_region_leader()

    def __translate_and_ensure_connect(self, destination: BullyPeer) -> str:
        target, ip, port = self.peer_translator[destination]

        if not self.has_connection(target):
            self.connect((ip, port))
        return target

    def __handle_bully_message(self, message: BullyPacket):
        try:
            target = self.__translate_and_ensure_connect(message.destination)
            self.send_message_no_wait(
                target=target,
                method="handle.region.bully.msg",
                body=_serialize_bully_packet(message),
            )
        except Exception:
            pass

    def __handle_bully_messages(self, messages: list[BullyPacket]):
        for message in messages:
            self.host.launch_background_thread(
                self.__handle_bully_message,
                function_args=(message,),
            )

    @node_handler(name="handle.region.bully.msg")
    def handle_bully_msg(self, body: dict, _sender: str):
        if hasattr(self.host, "can_participate_in_region_election"):
            if not self.host.can_participate_in_region_election():
                return {"status": "ignored", "reason": "region replica not election-ready"}

        decoded = _deser_bully_packet(body)
        self.__recv_poll(decoded)
        return {"status": "success"}

    def __recv_poll(self, message):
        self.node.receive(message)
        self.__handle_bully_messages(self.node.poll())

    @node_handler(internal_ms=50)
    def poll_internal_node(self):
        if hasattr(self.host, "can_participate_in_region_election"):
            if not self.host.can_participate_in_region_election():
                return
        self.__recv_poll(None)