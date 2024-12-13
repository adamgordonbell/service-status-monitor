from flask import Flask, render_template, jsonify, request
import requests
import schedule
import time
import threading
import toml
from scapy.all import sniff
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# Flask App
app = Flask(__name__)

app.logger.setLevel(logging.DEBUG)

# Load URLs from TOML
def load_urls_from_toml(file_path):
    config = toml.load(file_path)
    return config.get("services", {})

urls = load_urls_from_toml("urls_config.toml")
statuses = {url: {"status": "unknown", "description": "Checking..."} for url in urls.values()}
packet_stats = {"total_packets": 0, "http_requests": 0}

# Function to Check URL Status
def check_url_status(url):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json() if "json" in response.headers.get("Content-Type", "") else {}
            statuses[url] = {
                "status": data.get("status", {}).get("indicator", "ok"),
                "description": data.get("status", {}).get("description", "Operational")
            }
        else:
            statuses[url] = {"status": "critical", "description": "HTTP error"}
    except Exception as e:
        statuses[url] = {"status": "critical", "description": str(e)}

# Schedule URL Checks
def schedule_url_checks():
    for url in urls.values():
        schedule.every(30).seconds.do(lambda url=url: check_url_status(url))

# Scapy Packet Capture
def packet_callback(packet):
    global packet_stats
    packet_stats["total_packets"] += 1
    if packet.haslayer("HTTPRequest"):
        packet_stats["http_requests"] += 1

def start_packet_sniffer():
    sniff(prn=packet_callback, store=False, timeout=60)  # Capture packets every 60 seconds

# Scheduler Runner
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.before_request
def log_request_info():
    app.logger.debug(f"Request received: {request.method} {request.url}")
    app.logger.debug(f"Headers: {request.headers}")
    if request.data:
        app.logger.debug(f"Body: {request.data.decode('utf-8')}")


@app.after_request
def log_response_info(response):
    app.logger.debug(f"Response: {response.status} for {request.method} {request.url}")
    return response

# Flask Routes
@app.route("/")
def index():
    logging.info("index")
    return render_template("index.html")

@app.route("/status")
def status():
    return jsonify(statuses)

@app.route("/packet-stats")
def packet_stats_route():
    return jsonify(packet_stats)

if __name__ == "__main__":
    schedule_url_checks()
    threading.Thread(target=run_scheduler, daemon=True).start()
    threading.Thread(target=start_packet_sniffer, daemon=True).start()
    app.run(debug=True)
