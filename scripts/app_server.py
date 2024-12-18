from flask import Flask, render_template, jsonify, request, Response
import requests
import schedule
import time
import threading
import toml
from scapy.all import sniff
from scapy.packet import Packet
import logging
import argparse
from typing import Dict, Any, Optional, TypedDict, NoReturn

class ServiceStatus(TypedDict):
    status: str
    description: str

class ServiceDict(TypedDict):
    services: Dict[str, str]

class PacketStats(TypedDict):
    total_packets: int
    http_requests: int

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# Flask App
app = Flask(__name__, template_folder='../templates')  # Updated template folder path

app.logger.setLevel(logging.DEBUG)

# Load URLs from TOML
def load_urls_from_toml(file_path: str) -> Dict[str, str]:
    config: ServiceDict = toml.load(file_path)
    return config.get("services", {})

# Initialize empty URLs dict
urls: Dict[str, str] = {}
statuses: Dict[str, ServiceStatus] = {}
packet_stats: PacketStats = {"total_packets": 0, "http_requests": 0}

def initialize_urls() -> None:
    """Initialize URLs from config file if not already loaded"""
    global urls, statuses
    if not urls:
        try:
            app.logger.debug("Loading URLs from urls_config.toml")
            urls = load_urls_from_toml("urls_config.toml")
            app.logger.debug(f"Loaded URLs: {urls}")
            statuses = {url: {"status": "unknown", "description": "Checking..."} for url in urls.values()}
        except FileNotFoundError:
            app.logger.error("urls_config.toml not found in current directory")
            raise
        except Exception as e:
            app.logger.error(f"Error loading URLs: {str(e)}")
            raise

# Function to Check URL Status
def check_url_status(url: str) -> None:
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

# Scapy Packet Capture
def packet_callback(packet: Packet) -> None:
    global packet_stats
    packet_stats["total_packets"] += 1
    if packet.haslayer("HTTPRequest"):
        packet_stats["http_requests"] += 1

def start_packet_sniffer() -> None:
    sniff(prn=packet_callback, store=False, timeout=60)  # Capture packets every 60 seconds

# Scheduler Runner
def run_scheduler() -> NoReturn:
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.before_request
def log_request_info() -> None:
    app.logger.debug(f"Request received: {request.method} {request.url}")
    app.logger.debug(f"Headers: {request.headers}")
    if request.data:
        app.logger.debug(f"Body: {request.data.decode('utf-8')}")

@app.after_request
def log_response_info(response: Response) -> Response:
    app.logger.debug(f"Response: {response.status} for {request.method} {request.url}")
    return response

# Schedule URL Checks
def schedule_url_checks() -> None:
    app.logger.debug("Scheduling URL checks")
    for url in urls.values():
        app.logger.debug(f"Setting up schedule for {url}")
        schedule.every(30).seconds.do(lambda u=url: check_url_status(u))

# Flask Routes
@app.route("/")
def index() -> str:
    logging.info("index")
    return render_template("index.html")

@app.route("/status")
def status() -> Response:
    return jsonify(statuses)

@app.route("/packet-stats")
def packet_stats_route() -> Response:
    return jsonify(packet_stats)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-sniff', action='store_true', help='Disable packet sniffing')
    args = parser.parse_args()

    # Initialize URLs and schedule checks
    initialize_urls()
    schedule_url_checks()
    app.logger.info("Starting scheduler thread")
    threading.Thread(target=run_scheduler, daemon=True).start()
    
    if not args.no_sniff:
        app.logger.info("Starting packet sniffer thread")
        threading.Thread(target=start_packet_sniffer, daemon=True).start()
    else:
        app.logger.info("Packet sniffing disabled")
    
    app.run(debug=True, host='0.0.0.0', port=3000)
