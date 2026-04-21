from abc import abstractmethod
from hashlib import sha256
from json import dumps
import logging
import time
from typing import Any, Callable, Dict, List, Tuple

from colorama import Fore, Style
from pydantic import BaseModel

from backend.common.components.events.event import NodeEvent
from backend.common.components.plugins.leader_elec.bully_plugin import BullyPlugin
from backend.common.components.plugins.replication.replication_plugin import ReplicationPlugin
from backend.common.components.storage.backend import StorageBackend
from backend.common.components.util import NetworkEntry
from backend.common.layers.routing.routing_layer import node_handler
from backend.common.raw import RawNode


class KeyInfraNode(RawNode):
    def __init__(
        self,
        entry: NetworkEntry,
        peers: List[NetworkEntry],
        operation_routes: List[Tuple[str, Callable[..., Any]]],
        backend: StorageBackend,
    ):
        super().__init__(entry.name, entry.address.to_tuple())
        self.peers = [peer for peer in peers if peer.name != self.get_network_name()]
        self._logical_name = self._infer_logical_name(entry.name)

        self.leader_election = self.register_plugin(
            BullyPlugin(
                host=self,
                node=entry,
                peers=self.peers,
                heartbeat_interval_ms=8_000,
            )
        )

        self.replication_plugin = self.register_plugin(
            ReplicationPlugin(
                host=self,
                name=self.get_network_name(),
                backend=backend,
                replicas=[r.name for r in self.peers],
                routes=operation_routes,
            )
        )

        self.__state = self._default_state()
        loaded = self.replication_plugin.load_state()
        if loaded is not None:
            self.__state = self._parse_state(loaded)

    def on_operation(self):
        print("ON OP")
        if self.leader_election.current_leader() is not None and not self.leader_election.is_leader():
            self.leader_election.bump_leader_priority()

    def _infer_logical_name(self, node_name: str) -> str:
        if "-" not in node_name:
            return node_name
        base, suffix = node_name.rsplit("-", 1)
        return base if suffix.isdigit() else node_name

    def _node_kind(self) -> str:
        state_name = type(self.get_state()).__name__.lower()
        if "capital" in state_name:
            return "capital"
        if "region" in state_name:
            return "region"
        return "keyinfra"

    def _print_digest(self, name: str):
        state_dump: Dict = self.get_state().model_dump(mode="json")
        digest = sha256(dumps(state_dump, sort_keys=True).encode()).hexdigest()
        print(
            f"[{name}={Style.BRIGHT}{self.get_network_name()}{Style.RESET_ALL}] "
            f"State = {Fore.LIGHTBLACK_EX}{self.get_state()}{Fore.RESET} "
            f"{Fore.YELLOW}({digest[:4]}...){Fore.RESET} "
            f"{Fore.GREEN}(version={self.replication_plugin.get_seq_num()}){Fore.RESET}"
        )

    def get_state(self) -> BaseModel:
        return self.__state

    @node_handler(name="replication.version")
    def handle_replication_version(self, body):
        return {"version": self.replication_plugin.get_seq_num()}

    def election_state(self):
        bully = self.leader_election
        return {
            "name": self.get_network_name(),
            "version": self.replication_plugin.get_seq_num(),
            "leader": bully.current_leader(),
            "is_leader": bully.is_leader(),
            "election_in_progress": bully.bully_state.election_in_progress,
            "received_ok": bully.bully_state.received_ok,
            "updating_states": bully.bully_state.updating_states,
            "current_leader_peer": (
                bully.bully_state.current_leader.model_dump(mode="json")
                if bully.bully_state.current_leader is not None
                else None
            ),
            "peers": {
                name: peer.model_dump(mode="json")
                for name, peer in bully.node_map.items()
            },
        }

    @node_handler(name="query.node_status")
    def handle_query_node_status(self, body: dict):
        now = time.time()
        return {
            "id": self.get_network_name(),
            "kind": self._node_kind(),
            "logical_name": self._logical_name,
            "is_leader": self.leader_election.is_leader(),
            "leader_replica": self.leader_election.current_leader(),
            "version": self.replication_plugin.get_seq_num(),
            "status": "up",
            "last_seen_unix": now,
            "last_seen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        }

    @node_handler(name="ping.re")
    def handle_pingre(self, body: dict):
        return {
            "name": self.get_network_name(),
            "leader": self.leader_election.current_leader(),
        }

    @node_handler(internal_ms=1500)
    def pinger_int(self):
        for peer in self.peers:
            if peer.name == self.get_network_name():
                continue
            self._try_connect(peer)
            try:
                o = self.send_message(peer.name, "ping.re", {})
                if self.leader_election.current_leader() != o['leader']:
                    logging.error("DECTED A DISAGREEMENT!")
                    self.leader_election.start_election()
                logging.info(
                    f"[PING] [{self.get_network_name()} -> {peer.name}] "
                    f"Ping succeeded: {o} "
                    f"(local_leader={self.leader_election.current_leader()})"
                )
            except Exception:
                pass

    @node_handler(name="election.state")
    def handle_get_election_state(self, body: dict):
        print("GOT A GET ELECTION STATE CALL")
        state = self.election_state()
        return state.model_dump(mode="json") if hasattr(state, "model_dump") else state

    @node_handler(event=NodeEvent.ON_CONNECT)
    def handle_outbound_conn(self, name: str):
        print(f"{Fore.YELLOW}[CONNECTION]{Fore.RESET} Connected to {name} (type=OUTBOUND)")

    @node_handler(event=NodeEvent.ON_DISCONNECT)
    def handle_outbound_disconnect(self, name: str):
        print(f"DISCONNECTED FROM {name}")

    @node_handler(name="handle.catchup")
    def handle_catchup(self, body: dict):
        sequences = body["sequences"]
        return self.replication_plugin.serve_state_request(sequences)

    def on_new_version(self):
        self.leader_election.set_own_priority(self.replication_plugin.get_seq_num())

    def __run_challenge(self):
        pass

    def __on_elect(self, target: str):
        self.replication_plugin.set_leader(target)
        self.__run_challenge()

    def on_start_election(self):
        self.replication_plugin.set_leader(None)

    def on_become_leader(self):
        self.__on_elect(self.get_network_name())

    def on_elect_other(self, target):
        self.__on_elect(target)

    @abstractmethod
    def _default_state(self) -> BaseModel:
        pass

    @abstractmethod
    def _parse_state(self, data: Dict) -> BaseModel:
        pass