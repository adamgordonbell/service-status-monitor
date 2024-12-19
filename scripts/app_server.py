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
from typing import Dict, Any, Optional, TypedDict, NoReturn, Union
import json
from mangum import Mangum
from asgiref.wsgi import WsgiToAsgi

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
app = Flask(__name__, template_folder='../templates')  # Back to using relative path from scripts directory

# Convert Flask app to ASGI
asgi_app = WsgiToAsgi(app)

# Create the Lambda handler
handler = Mangum(asgi_app, lifespan="off")

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
        except FileNotFoundError:
            app.logger.warning("urls_config.toml not found, using default URLs")
            urls = {
                "github": "https://www.githubstatus.com/api/v2/status.json",
                "aws": "https://status.aws.amazon.com/healthcheck",
            }
        except Exception as e:
            app.logger.error(f"Error loading URLs: {str(e)}")
            urls = {}
        
        statuses = {url: {"status": "unknown", "description": "Checking..."} for url in urls.values()}

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
    app.logger.info(f"Received {request.method} request to path: {request.path}")
    app.logger.debug(f"Full URL: {request.url}")
    app.logger.debug(f"Headers: {dict(request.headers)}")
    app.logger.debug(f"Query Parameters: {dict(request.args)}")
    if request.data:
        app.logger.debug(f"Request Body: {request.data.decode('utf-8')}")

@app.after_request
def log_response_info(response: Response) -> Response:
    app.logger.info(f"Responding to {request.method} {request.path} with status {response.status_code}")
    app.logger.debug(f"Response Headers: {dict(response.headers)}")
    return response

# Flask Routes
@app.route("/")
def index() -> str:
    app.logger.info("Processing request to index /")
    
    # Debug: List contents of template directory
    import os
    template_dir = 'templates'
    app.logger.info(f"Looking for templates in: {template_dir}")
    if os.path.exists(template_dir):
        app.logger.info(f"Template directory contents: {os.listdir(template_dir)}")
    else:
        app.logger.error(f"Template directory {template_dir} does not exist!")
        
    # Also check current directory
    app.logger.info(f"Current directory: {os.getcwd()}")
    app.logger.info(f"Directory contents: {os.listdir('.')}")
    
    return render_template("index.html")

@app.route("/status")
def status() -> Response:
    app.logger.info("Processing request to /status")
    return jsonify(statuses)

@app.route("/packet-stats")
def packet_stats_route() -> Response:
    app.logger.info("Processing request to /packet-stats")
    return jsonify(packet_stats)

# AWS Lambda handler function
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function that processes API Gateway events
    """
    try:
        app.logger.debug(f"Lambda event: {json.dumps(event)}")
        
        # Initialize URLs if needed
        initialize_urls()
        
        # Handle the request using Mangum
        response = handler(event, context)
        app.logger.debug(f"Response: {response}")
        return response
    except Exception as e:
        logging.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {
                "Content-Type": "application/json"
            }
        }

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
