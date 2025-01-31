from flask import Flask, jsonify, request
from mangum import Mangum

app = Flask(__name__)

@app.route("/hello")
def hello():
    return jsonify({"message": "Hello from Flask!"})

@app.route("/echo", methods=['POST'])
def echo():
    data = request.get_json()
    return jsonify({"reversed": data['message'][::-1]})

lambda_handler = Mangum(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
