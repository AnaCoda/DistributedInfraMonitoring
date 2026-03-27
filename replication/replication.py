# # Capital server
# # - Flask HTTP API on port 5000  (frontend talks here)
# # - TCP listener on port 6000    (regional nodes talk here)
# # - Replication listener on port 4000+


# # All Imports
# from flask import Flask, jsonify, request
# from flask_cors import CORS
# import threading
# import requests
# import time
# import random
# import sys # for getting port number via standard input


# # Variables Needed
# CAPITAL_URL = "http://localhost:5000/api/national_infrastructure" # This is the URL of the capitals national_infrastructure returning service
# national_infrastructure = {} # This is what we are replicating


# # Flask Stuff
# app = Flask(__name__)
# CORS(app)


# # Client prompts this to get the national infrastructure
# @app.route("/api/national_infrastructure")
# def get_national_status():
#     return jsonify(national_infrastructure)


# # This is what pulls the data from the capital
#     # Random time is used for realism, and also desynchronisation
# def sync_with_capital():
#     global national_infrastructure

#     while True:
#         try:
#             response = requests.get(CAPITAL_URL)          
#             national_infrastructure = response.json()       
#             print("Synced with capital.")
#         except Exception as exception:
#             print("Sync failed:", exception)

#         time.sleep(random.randint(0,10))



# if __name__ == "__main__":
#     PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
#     if len(sys.argv) == 1:
#         print("Please use format 'python replication.py 4001' to denote port number.")
#     threading.Thread(target=sync_with_capital, daemon=True).start()
#     app.run(port=PORT)
