import threading
import random
import sys
import websockets
import json
import os
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.shared.node import NodeBase, node_handler, NodeConnectionType, _send_raw
from typing import Optional


# will be creating multiples of these for active replication
class ReplicationManager(NodeBase):
    def __init__(self, manager_id, address, capital_address: tuple[str, int]):

        super().__init__(
            network_name=f"rm-{manager_id}",
            address = address
        )


        self.manager_id = manager_id        
        self.capital_address = capital_address
        self.received_messages = []
        self.state = {}
        self.heartbeats = {}

    def _start(self):
        """connect to capital"""

        self.connect(self.capital_address)

        print(f"[{self.network_name}] connected to capital")

    @node_handler(name='push.state_update')
    def handle_state_update(self, body: dict, sender: str): 
        """when capital node pushes out a state update, update these accordingly and push to clients"""

        # store state, heartbeats from payload
        self.state = body["state"]
        self.heartbeats = body["heartbeats"]
        print(f"[{self.network_name}] state updated from {sender}")

        # pass to client
        self._broadcast_state()

    @node_handler(name='api.national_infrastructure')
    def get_national_status(self, _message):
        return {
            "state": self.state,
            "heartbeats": self.heartbeats,
        }


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