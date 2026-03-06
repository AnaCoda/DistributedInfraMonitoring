# # Capital server
# # - Flask HTTP API on port 5000  (frontend talks here)
# # - TCP listener on port 6000    (regional nodes talk here)
from ..shared.node import NodeBase, node_handler
import threading
import datetime

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
        super().__init__(network_name, address)
        
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
            
        }
    
    @node_handler(name='api.hello')
    def handle_hello(self, message):
        return {
            "message": "Hello from the capital server!"
        }
        
    @node_handler(name='api.region.heartbeat')
    def handle_region_heartbeat(self, message: dict, source: str):
        print(f'Received heartbeat from {source}')
        if source not in self.heart_beat:
            self.heart_beat[source] = {}
        self.heart_beat[source]['last_contact'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
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
            raise RuntimeError("Missing name or state.")
        
        # This does the update if everything is working
        with self.lock:
            # Updates overview of all states
            self.national_infrastructure[state_name] = state_data

            # if updated state is the capital then update it's local one as well
            if state_name == "Capital":
                self.state_infrastructure = state_data
        return {"message":f"State {state_name} updated successfully."}



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
