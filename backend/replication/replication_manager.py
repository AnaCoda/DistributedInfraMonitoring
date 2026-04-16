import threading
import random
import sys
import json
import os
import uuid

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ..shared.node import NodeBase, node_handler, NodeConnectionType, _send_raw
from ..shared.node import NodeRpcError
from typing import Optional


# will be creating multiples of these for active replication
class ReplicationManager(NodeBase):
    def __init__(self, manager_id, address, capital_address: tuple[str, int]):
        self._capital_connect_lock = threading.Lock()

        super().__init__(
            network_name=f"rm-{manager_id}",
            address = address
        )


        self.manager_id = manager_id        
        self.capital_address = capital_address
        self.received_messages = []
        self.state = {}
        self.heartbeats = {}
        self.synced = False
        self.sync_event = threading.Event()

    def _start(self):
        """connect to capital"""
        self.ensure_capital_connection()

        print(f"[{self.network_name}] connected to capital")

    @node_handler(internal_ms=1000)
    def ensure_connected(self):
        self.ensure_capital_connection()

    def ensure_capital_connection(self):
        if self.is_outage_active():
            return

        with self._capital_connect_lock:
            if self.has_connection("Capital"):
                return

            try:
                self.connect(self.capital_address)
            except Exception:
                pass

    @node_handler(name='push.state_update')
    def handle_state_update(self, body: dict, sender: str): 
        """when capital node pushes out a state update, update these accordingly and push to clients"""

        # store state, heartbeats from payload
        self.state = body["state"]
        self.heartbeats = body["heartbeats"]
        # print(f"[{self.network_name}] state updated from {sender}")

        self.synced = True
        self.sync_event.set()

        # pass to client
        self._broadcast_state()

    @node_handler(name='api.national_infrastructure')
    def get_national_status(self, _message):
        while not self.synced:
            self.sync_event.wait()
        return {
            "state": self.state,
            "heartbeats": self.heartbeats,
        }

    @node_handler(name='admin.simulated_fail_packet')
    def forward_admin_fail_packet(self, body: dict, sender: str):
        if not sender.startswith("Frontend-"):
            raise NodeRpcError("Only frontend clients may issue admin fail packets via replication manager.")

        return self.send_message("Capital", "admin.simulated_fail_packet", body)

    @node_handler(name='admin.node.outage_control')
    def handle_admin_node_outage_control(self, body: dict):
        return NodeBase.handle_node_outage_control(self, body)


    def _broadcast_state(self):
        """push states to all frontend clients"""
        payload = {
            "route": "push.replica_state_update",
            "rid": str(uuid.uuid4()),
            "body": {
                "state": self.state,
                "heartbeats": self.heartbeats
            }
        }
        dead = []
        for name, entry in list(self.inbound_connections.items()):
            if name.startswith("Frontend-"): # send to frontends
                try:
                    _send_raw(entry.connection, payload)
                except Exception:
                    dead.append(name)
        for name in dead:
            self.inbound_connections.pop(name, None)