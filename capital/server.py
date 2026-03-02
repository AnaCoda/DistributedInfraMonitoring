# Capital server
# - Flask HTTP API on port 5000  (frontend talks here)
# - TCP listener on port 6000    (regional nodes talk here)

from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route("/api/hello")
def hello():
    return jsonify({"message": "Hello from the capital server!"})

if __name__ == "__main__":
    app.run(port=5000, debug=True)
