# Capital server
# - Flask HTTP API on port 5000  (frontend talks here)
# - TCP listener on port 6000    (regional nodes talk here)

from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time

from capital.capital_tcp_node import CapitalTcpNode

# This contains the states unique name (must be unique for logical reasons)
    # if 2 states share a name the system will treat 2 unique geographic entities as 1
    # should not cause code issues, but will be confusing for the user
name = "Capital"

# This signifies the infrastructural state of the capital region
state_infrastructure = {
    "power":"stable",               # Either stable or unstable
    "medical_capacity":100,         # % of available beds
    "transport":"operational",      # Are the roads / airports working
    "water_capacity":100,           # % of water required available
    "fuel_storage":100              # % of fuel required available
}

# This is the centralised record for how all states are faring
national_infrastructure = {
    "Capital": state_infrastructure
}

app = Flask(__name__)
CORS(app)


# More shit to implment tcp instead of http this entire file needs an overhaul
lock = threading.Lock()
tcp_node = CapitalTcpNode(
    network_name="Capital",
    address=("127.0.0.1", 6000), # Hardcoded for testing please dont leave this here
    national_store=national_infrastructure,
    store_lock=lock,
)

@app.route("/api/hello")
def hello():
    return jsonify({"message": "Hello from the capital server!"})

# This will allow the server to return the status of the Capital areas state infrastructure
    # This is a dictionary being returned
@app.route("/api/state_infrastructure")
def get_capital_status():
    return jsonify(state_infrastructure)

# This will allow the server to return the status of the national infrastructure
    # This is a dictionary, with the state name as the key, and it's local dictionary as the value
@app.route("/api/national_infrastructure")
def get_national_status():
    return jsonify(national_infrastructure)


# This creates a lock to prevent race conditions on update procedures
lock = threading.Lock()

# The lock is used for the updating section of the API calls
    # if you need to do something other than read it is hidden behind this lock
@app.route("/api/update_state", methods=["POST"])
def update_state():
    # collect the data
    data = request.json
    state_name = data.get("name")
    state_data = data.get("state")

    # return errors just in case there's an issue
    if not state_name or not state_data:
        return jsonify({"error":"Missing name or state"}), 400
    
    # This does the update if everything is working
    with lock:
        # Updates overview of all states
        national_infrastructure[state_name] = state_data

        # if updated state is the capital then update it's local one as well
        if state_name == "Capital":
            global state_infrastructure 
            state_infrastructure = state_data
    return jsonify({"message":f"State {state_name} updated successfully."}), 200


if __name__ == "__main__":
    app.run(port=5000, debug=True)
