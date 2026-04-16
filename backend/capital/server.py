# # Capital server
# # - Flask HTTP API on port 5000  (frontend talks here)
# # - TCP listener on port 6000    (regional nodes talk here)
from ..shared.node import NodeBase, node_handler, _send_raw, NodeRpcError
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

class CapitalNode(NodeBase):
    def __init__(self, network_name, address):
        self.lock = threading.Lock()
        
        self.state_infrastructure = {
            "power":"stable",               # Either stable or unstable
            "medical_capacity":100,         # % of available beds
            "transport":"operational",      # Are the roads / airports working
            "water_capacity":100,           # % of water required available
            "fuel_storage":100              # % of fuel required available
        }
        
        self.national_infrastructure = {
            "Capital": {
                "state": self.state_infrastructure,
                "meta": {
                    "region_type": "CapitalNode",
                    "sites": [],
                },
            }
        }
        
        self.heart_beat = {
            "Capital": {
                "last_contact": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
        }
        self.control_overrides = {
            "replication": {},
            "regional": {},
        }

        super().__init__(network_name, address)
    
    @node_handler(name='api.hello')
    def handle_hello(self, message):
        return {
            "message": "Hello from the capital server!"
        }
        
    @node_handler(name='api.region.heartbeat')
    def handle_region_heartbeat(self, message: dict, source: str):
        # print(f'Received heartbeat from {source}')
        if source not in self.heart_beat:
            self.heart_beat[source] = {}
        self.heart_beat[source]['last_contact'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._broadcast_state()

    @node_handler(internal_ms=1000)
    def self_heartbeat(self):
        if not hasattr(self, "heart_beat") or not hasattr(self, "national_infrastructure"):
            return
        self.heart_beat.setdefault("Capital", {})
        self.heart_beat["Capital"]["last_contact"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._broadcast_state()

    @node_handler(name="api.state_infrastructure")
    def get_capital_status(self, _m):
        return self.state_infrastructure
    
    @node_handler(name="api.national_infrastructure")
    def get_national_status(self, _m):
        return {
            'state': self.national_infrastructure,
            'heartbeats': self.heart_beat
        }
    
    @node_handler(name="api.update_state")
    def update_state(self, data):
        # collect the data
        state_name = data["name"]
        state_data = data["state"]

        # return errors just in case there's an issue
        if not state_name or not state_data:
            raise NodeRpcError("Missing name or state.")
        
        # This does the update if everything is working
        with self.lock:
            # Updates overview of all states
            self.national_infrastructure[state_name] = state_data

            # if updated state is the capital then update it's local one as well
            if state_name == "Capital":
                self.state_infrastructure = state_data

        self._broadcast_state()
        return {"message":f"State {state_name} updated successfully."}

    @node_handler(name="admin.simulated_fail_packet")
    def handle_admin_fail_packet(self, body: dict, source: str):
        target_id = str(body.get("target_id") or "").strip()
        try:
            duration_sec = float(body.get("duration_sec", 0))
        except (TypeError, ValueError):
            raise NodeRpcError("duration_sec must be a number greater than 0.")

        if not target_id:
            raise NodeRpcError("Missing target_id.")
        if duration_sec <= 0:
            raise NodeRpcError("duration_sec must be greater than 0.")

        if target_id.lower() == self.network_name.lower():
            self.begin_outage(duration_sec)
            return {
                "status": "success",
                "source": source,
                "target_id": self.network_name,
                "duration_sec": duration_sec,
            }

        if "/" in target_id:
            region_name_raw, infra_name_raw = target_id.split("/", 1)
            region_name = region_name_raw.strip()
            infra_name = infra_name_raw.strip()
            if not region_name or not infra_name:
                raise NodeRpcError("Infrastructure targets must use '<RegionName>/<SiteName>' format.")

            resolved_region = next((name for name in self.outbound_connections.keys() if name.lower() == region_name.lower()), None)
            if resolved_region is None:
                raise NodeRpcError(f"Regional target '{region_name}' is not connected.")

            response = self.send_message(
                target=resolved_region,
                method="admin.region.route_node_outage",
                body={
                    "target_id": infra_name,
                    "duration_sec": duration_sec,
                }
            )
            return {
                "status": "success",
                "source": source,
                "target_id": f"{resolved_region}/{infra_name}",
                "duration_sec": duration_sec,
                "downstream": response,
            }

        resolved_target = next((name for name in self.outbound_connections.keys() if name.lower() == target_id.lower()), None)
        if resolved_target is None:
            raise NodeRpcError(f"Target '{target_id}' is not connected.")

        response = self.send_message(
            target=resolved_target,
            method="admin.node.outage_control",
            body={
                "duration_sec": duration_sec,
            }
        )

        return {
            "status": "success",
            "source": source,
            "target_id": resolved_target,
            "duration_sec": duration_sec,
            "downstream": response,
        }

    def _broadcast_state(self):
        """Push current state to all connected replication manager clients."""
        payload = {
            "route": "push.state_update",
            "rid": str(uuid.uuid4()),
            "body": {
                "state": self.national_infrastructure,
                "heartbeats": self.heart_beat,
            }
        }
        dead = []
        for name, entry in list(self.inbound_connections.items()):
            if name.startswith("rm-"): # send to replication managers
                try:
                    _send_raw(entry.connection, payload)
                except Exception:
                    dead.append(name)
        for name in dead:
            self.inbound_connections.pop(name, None)



# # This signifies the infrastructural state of the capital region
# state_infrastructure = {
#     "power":"stable",               # Either stable or unstable
#     "medical_capacity":100,         # % of available beds
#     "transport":"operational",      # Are the roads / airports working
#     "water_capacity":100,           # % of water required available
#     "fuel_storage":100              # % of fuel required available
# }

# # This is the centralised record for how all states are faring
# national_infrastructure = {
#     "Capital": state_infrastructure
# }

# app = Flask(__name__)
# CORS(app)

# @app.route("/api/hello")
# def hello():
#     return jsonify({"message": "Hello from the capital server!"})

# # This will allow the server to return the status of the Capital areas state infrastructure
#     # This is a dictionary being returned
# @app.route("/api/state_infrastructure")
# def get_capital_status():
#     return jsonify(state_infrastructure)

# # This will allow the server to return the status of the national infrastructure
#     # This is a dictionary, with the state name as the key, and it's local dictionary as the value
# @app.route("/api/national_infrastructure")
# def get_national_status():
#     return jsonify(national_infrastructure)


# # This creates a lock to prevent race conditions on update procedures
# lock = threading.Lock()

# # The lock is used for the updating section of the API calls
#     # if you need to do something other than read it is hidden behind this lock
# @app.route("/api/update_state", methods=["POST"])
# def update_state():
#     # collect the data
#     data = request.json
#     state_name = data.get("name")
#     state_data = data.get("state")

#     # return errors just in case there's an issue
#     if not state_name or not state_data:
#         return jsonify({"error":"Missing name or state"}), 400
    
#     # This does the update if everything is working
#     with lock:
#         # Updates overview of all states
#         national_infrastructure[state_name] = state_data

#         # if updated state is the capital then update it's local one as well
#         if state_name == "Capital":
#             global state_infrastructure 
#             state_infrastructure = state_data
#     return jsonify({"message":f"State {state_name} updated successfully."}), 200


# if __name__ == "__main__":
#     app.run(port=5000, debug=True)
