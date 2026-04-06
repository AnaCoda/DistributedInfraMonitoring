# # Capital server
# # - Flask HTTP API on port 5000  (frontend talks here)
# # - TCP listener on port 6000    (regional nodes talk here)
from ..shared.node import NodeBase, node_handler, _send_raw, NodeConnectionType
from ..common.patching.patch import Patch
from ..common.patching.mpatch import ManagedState, VersionedPatch
import threading
import datetime
import uuid

# from flask import Flask, jsonify, request
# from flask_cors import CORS
# import threading
# import time

# # This contains the states unique name (must be unique for logical reasons)
#     # if 2 states share a name the system will treat 2 unique geographic entities as 1
#     # should not cause code issues, but will be confusing for the user
# name = "Capital"

import hashlib

def _source_manager() -> ManagedState:
    state_infrastructure = {
            "power":"stable",               # Either stable or unstable
            "medical_capacity":100,         # % of available beds
            "transport":"operational",      # Are the roads / airports working
            "water_capacity":100,           # % of water required available
            "fuel_storage":100              # % of fuel required available
        }
    return ManagedState.from_dict(1, {
            "heartbeat": {

            },
            "state": {
                "Capital": {
                    "state": state_infrastructure,
                    "meta": {
                        "region_type": "CapitalNode",
                        "sites": []
                    }
                }
            }
        })

class CapitalNode(NodeBase):
    def __init__(self, network_name, leader_address, address, leader_name: str, replica: bool = False):
        
        self.ready = not replica
        self.ready_evt = threading.Event()
        super().__init__(network_name, address)

        self.replica = replica
        self.leader_name = leader_name
        
        self.lock = threading.Lock()
        self.proxy_lock = threading.Lock()

        self.leader_address = leader_address

        self.replica_state = _source_manager() if not replica else ManagedState(version=0)

        if replica:
            self.connect(self.leader_address)
            print(f'[{self.network_name}] Has connected to the capital.')

    def __proxy_call(self, call, proxy_name: str, data, source = None):
        with self.proxy_lock:
            a, result = call(data, source)
            if result is not None:
                self.multicast('rm-*', proxy_name, data, include_self=False)
        return a

    @node_handler(on_connect=NodeConnectionType.OUTBOUND)
    def on_connect(self, name):
        if name == self.leader_name:
            # We need to update the state.
            rs = self.send_message(self.leader_name, 'fast.forward', {})

            self.replica_state.fast_forward(rs['__version'], rs['__state'])
            self.ready = True
            self.ready_evt.set()
            print(f'[{self.network_name}] Fast-forwarded to version={self.replica_state.version}')


    @node_handler(name='fast.forward')
    def handle_fast_forward(self, message):
        return {
            "__version": self.replica_state.version,
            "__state": self.replica_state.inspect_dict()
        }
    
  
    @node_handler(name='push.state_update')
    def handle_state_update(self, body: dict, sender: str):
        # print('Received a state update...')
        
        version = VersionedPatch.from_dict(body)
        
        self.replica_state.apply_update(version)
        # print(f'[{self.network_name}] Received version={version.version}, at={self.replica_state.version}')
        if self.replica_state.is_consistent():
            self.sync_evt.set()

            import json
            serialized = json.dumps(
                obj=self.replica_state.inspect_dict(),
                default=lambda x : str(x)
            )
            print(f'[{self.network_name}] version={self.replica_state.version}, data={hashlib.sha256(serialized.encode()).hexdigest()}')

    def __handle_heartbeat(
        self,
        _data,
        source: str
    ):
        state = self.replica_state.start_transaction()
        if source not in state['heartbeat']:
            state['heartbeat'][source] = {}
        state['heartbeat'][source]['last_contact'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return None, self.replica_state.end_transaction(state)
    

    
    @node_handler(name="api.national_infrastructure")
    def get_national_status(self, _m):
        while not self.ready:
            self.ready_evt.wait()        
        while not self.replica_state.is_consistent():
            self.sync_event.wait()


        return self.replica_state.inspect_dict()

    def __commit_local_replica(self, data: dict):
        # import copy
        # og = copy.deepcopy(self.replica_state.inspect_dict())
        result = self.replica_state.end_transaction(data, apply=True)
        # self.replica_state.apply_update(result)
        # print(f'now {og == self.replica_state.inspect_dict()}')
        import json
        serialized = json.dumps(
            obj=self.replica_state.inspect_dict(),
            default=lambda x : str(x)
        )
        print(f'[{self.network_name}] version={self.replica_state.version}, data={hashlib.sha256(serialized.encode()).hexdigest()}')
        return result
    
    def __handle_operation(self, data, _src):
        # collect the data
        state_name = data["name"]
        state_data = data["state"]

        # return errors just in case there's an issue
        if not state_name or not state_data:
            raise RuntimeError("Missing name or state.")
        
        # This does the update if everything is working
        with self.lock:
            trs = self.replica_state.start_transaction()

            # import copy

            # og = copy.deepcopy(trs)
            # print(f'yoo: {state_data}')
            # Updates overview of all states
            trs['state'][state_name] = state_data

            # print(f'same {og == trs}')

            
            rs = self.__commit_local_replica(trs)
            return state_name, rs
        

    @node_handler(name='api.proxy.region.heartbeat')
    def handle_region_heartbeat_pxy(self, message: dict, source: str):
        self.__handle_heartbeat(message, source)

    @node_handler(name='api.region.heartbeat')
    def handle_region_heartbeat(self, message: dict, source: str):
        self.__proxy_call(
            call=self.__handle_heartbeat,
            proxy_name='api.proxy.region.heartbeat',
            data=message,
            source=source      
        )

    @node_handler(name='api.proxy.state_update')
    def handle_operation(self, data):
        state_name, _ = self.__handle_operation(data, None)
        return {"message":f"State {state_name} updated successfully."}
    
    @node_handler(name="api.update_state")
    def update_state(self, data):
        self.__proxy_call(
            call=self.__handle_operation,
            proxy_name='api.proxy.state_update',
            data=data         
        )
