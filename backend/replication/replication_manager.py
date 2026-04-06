import threading
import uuid
from typing import Optional

from ..shared.node import NodeBase, node_handler, _send_raw
from ..shared.leader_election import BullyElectionMixin


class ReplicationManager(BullyElectionMixin, NodeBase):
    def __init__(
        self,
        manager_id: int,
        address,
        peer_addresses: dict[int, tuple[str, int]],
    ):
        self.manager_id = manager_id
        self.peer_addresses = peer_addresses

        # Pre-initialize election fields BEFORE NodeBase starts interval threads
        self.node_id = manager_id
        self.peer_names = [f"rm-{rid}" for rid in peer_addresses.keys() if rid != manager_id]

        self.is_leader = False
        self.current_leader = None

        self.heartbeat_interval_ms = 1000
        self.leader_timeout_ms = 3000

        import time
        self.last_leader_heartbeat = time.time()

        self.election_lock = threading.Lock()
        self.election_in_progress = False
        self.received_ok = False
        self.awaiting_coordinator = False
        self.coordinator_deadline = None

        super().__init__(
            network_name=f"rm-{manager_id}",
            address=address
        )

        self.received_messages = []
        self.state = {}
        self.heartbeats = {}

        self.synced = False
        self.sync_event = threading.Event()

        self.state_version = 0

    def _start(self):
        """
        Connect to all peers. If a leader exists, follow it.
        Only start election if no leader can be discovered.
        """
        for rid, addr in self.peer_addresses.items():
            if rid == self.manager_id:
                continue
            try:
                self.connect(addr)
                print(f"[{self.network_name}] connected to peer rm-{rid}")
            except Exception as e:
                print(f"[{self.network_name}] could not connect to peer rm-{rid}: {e}")

        import time
        time.sleep(1)

        leader = self.discover_current_leader()
        if leader:
            return

        self.start_election()

    @node_handler(internal_ms=1000)
    def election_tick(self):
        if not hasattr(self, "is_leader"):
            return
        self.step_election()

    @node_handler(internal_ms=2000)
    def peer_reconnect_tick(self):
        for rid, addr in self.peer_addresses.items():
            if rid == self.manager_id:
                continue

            peer_name = f"rm-{rid}"
            if self.has_connection(peer_name):
                continue

            try:
                self.connect(addr)
                print(f"[{self.network_name}] reconnected to peer {peer_name}")
            except Exception:
                try:
                    if self.has_connection(peer_name):
                        self.disconnect(peer_name)
                except Exception:
                    pass
                continue

    @node_handler(internal_ms=2500)
    def leader_sync_tick(self):
        if not self.is_leader:
            self.try_refresh_from_leader()

    def try_refresh_from_leader(self):
        if not self.current_leader:
            return

        if not self.has_connection(self.current_leader):
            return

        try:
            resp = self.send_message(self.current_leader, "api.national_infrastructure", {}, timeout=1.0)
            self.state = resp.get("state", self.state)
            self.heartbeats = resp.get("heartbeats", self.heartbeats)
            self.state_version = resp.get("version", self.state_version)
            self.synced = True
            self.sync_event.set()
        except Exception:
            pass

    @node_handler(name="api.who_is_leader")
    def who_is_leader(self, _body: dict):
        return {
            "leader": self.current_leader,
            "is_leader": self.is_leader,
            "self": self.network_name,
        }

    @node_handler(name="api.update_state")
    def handle_write_update(self, body: dict, sender: str):
        """
        Only leader should accept writes from regions in the demo architecture.
        Followers reject.
        """
        if not self.is_leader:
            return {
                "status": "fail",
                "reason": f"not leader; current leader is {self.current_leader}"
            }

        name = body["name"]
        state_blob = body["state"]

        self.state[name] = state_blob
        self.state_version += 1
        self.synced = True
        self.sync_event.set()

        self.replicate_full_state()
        self._broadcast_state()

        return {
            "status": "success",
            "leader": self.network_name,
            "version": self.state_version,
        }

    @node_handler(name="api.region.heartbeat")
    def handle_region_heartbeat(self, body: dict, sender: str):
        if not self.is_leader:
            return {
                "status": "fail",
                "reason": f"not leader; current leader is {self.current_leader}"
            }

        import datetime
        if sender not in self.heartbeats:
            self.heartbeats[sender] = {}
        self.heartbeats[sender]["last_contact"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        self.replicate_full_state()
        self._broadcast_state()

        return {"status": "success"}

    @node_handler(name="replica.state_update")
    def handle_replica_state_update(self, body: dict, sender: str):
        version = int(body.get("version", 0))
        if version < self.state_version:
            return {"status": "stale_ignored"}

        self.state = body.get("state", {})
        self.heartbeats = body.get("heartbeats", {})
        self.state_version = version
        self.synced = True
        self.sync_event.set()

        self._broadcast_state()
        return {"status": "success"}

    @node_handler(name='api.national_infrastructure')
    def get_national_status(self, _message):
        while not self.synced:
            self.sync_event.wait()
        return {
            "state": self.state,
            "heartbeats": self.heartbeats,
            "leader": self.current_leader,
            "is_leader": self.is_leader,
            "version": self.state_version,
        }

    def replicate_full_state(self):
        if not self.is_leader:
            return

        payload = {
            "version": self.state_version,
            "state": self.state,
            "heartbeats": self.heartbeats,
            "leader": self.network_name,
        }

        for peer in self.connected_peer_names():
            try:
                self.send_message(
                    target=peer,
                    method="replica.state_update",
                    body=payload,
                    timeout=1.0,
                )
            except Exception as e:
                print(f"[{self.network_name}] failed replicating to {peer}: {e}")

    def _broadcast_state(self):
        payload = {
            "route": "push.replica_state_update",
            "rid": str(uuid.uuid4()),
            "body": {
                "state": self.state,
                "heartbeats": self.heartbeats,
                "leader": self.current_leader,
                "is_leader": self.is_leader,
                "version": self.state_version,
            }
        }

        dead = []
        for name, entry in list(self.inbound_connections.items()):
            if name.startswith("Frontend-"):
                try:
                    _send_raw(entry.connection, payload)
                except Exception:
                    dead.append(name)

        for name in dead:
            self.inbound_connections.pop(name, None)