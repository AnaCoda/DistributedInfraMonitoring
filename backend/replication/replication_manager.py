import threading
import random
import sys
import websockets
import json
import os
from ..common.patching.mpatch import ManagedState, VersionedPatch
import uuid

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ..shared.node import NodeBase, node_handler, NodeConnectionType, _send_raw
from typing import Optional


# will be creating multiples of these for active replication
class ReplicationManager(NodeBase):
    def __init__(self, manager_id, address, capital_address: tuple[str, int]):

        super().__init__(
            network_name=f"rm-{manager_id}",
            address = address
        )

        self.manager = ManagedState(version=0)

        self.manager_id = manager_id        
        self.capital_address = capital_address
        self.received_messages = []
        self.state = {}
        self.heartbeats = {}
        self.synced = False
        self.sync_event = threading.Event()

        self.ready = False
        self.ready_evt = threading.Event()
        
        

    def _start(self):
        """connect to capital"""

        self.connect(self.capital_address)

        print(f"[{self.network_name}] connected to capital")

    @node_handler(on_connect=NodeConnectionType.OUTBOUND)
    def on_connect(self, name):
        if name == 'Capital':
            # We need to update the state.
            rs = self.send_message('Capital', 'fast.forward', {})
            # print(f"YAY {rs}")
            self.manager.fast_forward(rs['__version'], rs['__state'])
            self.ready = True
            self.ready_evt.set()
            print(f'[{self.network_name}] Fast-forwarded to version={self.manager.version}')

    @node_handler(name='push.state_update')
    def handle_state_update(self, body: dict, sender: str): 
        """when capital node pushes out a state update, update these accordingly and push to clients"""


        # print(f'received some state update')
        # print(f'State: {body}')
        version = VersionedPatch.from_dict(body)
        # print(f'Version: {version}')
       
        # version = VersionedPatch.from_dict(body)
        self.manager.apply_update(version)
        # print(f'[{self.network_name}] Version = {self.manager.version}')
        # # print(f'body: {body}')
        # # store state, heartbeats from payload
        # # self.state = body["state"]
        # # self.heartbeats = body["heartbeats"]
        # # print(f"[{self.network_name}] state updated from {sender}")

        # self.synced = True
        # self.sync_event.set()

        # # pass to client
        # self._broadcast_state()

    @node_handler(name='api.national_infrastructure')
    def get_national_status(self, _message):
        while not self.synced:
            self.sync_event.wait()
        return {
            "state": self.state,
            "heartbeats": self.heartbeats,
        }


    # def _broadcast_state(self):
    #     """push states to all frontend clients"""
    #     payload = {
    #         "route": "push.replica_state_update",
    #         "rid": str(uuid.uuid4()),
    #         "body": {
    #             "state": self.state,
    #             "heartbeats": self.heartbeats
    #         }
    #     }
    #     dead = []
    #     for name, entry in list(self.inbound_connections.items()):
    #         if name.startswith("Frontend-"): # send to frontends
    #             try:
    #                 _send_raw(entry.connection, payload)
    #             except Exception:
    #                 dead.append(name)
    #     for name in dead:
    #         self.inbound_connections.pop(name, None)