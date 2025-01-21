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
from typing import Dict, Any, TypedDict, NoReturn
import json
from mangum import Mangum
import os
from asgiref.wsgi import WsgiToAsgi

class ServiceStatus(TypedDict):
    status: str
    description: str


class ServiceDict(TypedDict):
    services: Dict[str, str]


class PacketStats(TypedDict):
    total_packets: int
    http_requests: int


# Create Flask app
app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app.logger.setLevel(logging.DEBUG)

# Define environments
ENVIRONMENTS = ["prod", "candidate", "stable"]

@app.route('/<environment>/', methods=['GET'])
def root(environment):
    if environment not in ENVIRONMENTS:
        return jsonify({"message": "Not Found"}), 404
    try:
        return render_template('index.html')
    except Exception as e:
        app.logger.error(f"Error rendering template: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

@app.route('/<environment>/status', methods=['GET'])
def status(environment):
    if environment not in ENVIRONMENTS:
        return jsonify({"message": "Not Found"}), 404
    try:
        return jsonify(statuses)
    except Exception as e:
        app.logger.error(f"Error getting status: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

@app.route('/<environment>/packet-stats', methods=['GET'])
def packet_stats_route(environment):
    if environment not in ENVIRONMENTS:
        return jsonify({"message": "Not Found"}), 404
    try:
        app.logger.debug("Getting packet stats")
        return jsonify(get_packet_stats())
    except Exception as e:
        app.logger.error(f"Error getting packet stats: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

# Convert Flask app to ASGI
asgi_app = WsgiToAsgi(app)

# Configure Mangum handler
handler = Mangum(asgi_app, lifespan="off")

# Add middleware to strip environment prefix
@app.before_request
def strip_path_prefix():
    # Extract the path without query string
    path = request.path
    app.logger.debug(f"Original request path: {path}")
    app.logger.debug(f"Request environment: {request.environ}")

    # Strip environment prefix if present
    for prefix in ["/prod/", "/candidate/", "/stable/"]:
        if path.startswith(prefix):
            # Remove the prefix but keep the rest
            path = "/" + path[len(prefix) :] if len(path) > len(prefix) else "/"
            app.logger.debug(f"Modified request path: {path}")
            request.environ["PATH_INFO"] = path
            request.environ["SCRIPT_NAME"] = prefix[:-1]  # Remove trailing slash
            break

    app.logger.debug(f"Final request path: {request.environ['PATH_INFO']}")
    app.logger.debug(f"Script name: {request.environ.get('SCRIPT_NAME', '')}")

# Load URLs from TOML
def load_urls_from_toml(file_path: str) -> Dict[str, str]:
    try:
        config: Dict[str, Dict[str, str]] = toml.load(file_path)
        return config.get("services", {})
    except Exception as e:
        app.logger.error(f"Error loading URLs: {str(e)}")
        return {}

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

        statuses = {
            url: {"status": "unknown", "description": "Checking..."}
            for url in urls.values()
        }

# Function to Check URL Status
def check_url_status(url: str) -> None:
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = (
                response.json()
                if "json" in response.headers.get("Content-Type", "")
                else {}
            )
            statuses[url] = {
                "status": data.get("status", {}).get("indicator", "ok"),
                "description": data.get("status", {}).get("description", "Operational"),
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
    sniff(
        prn=packet_callback, store=False, timeout=60
    )  # Capture packets every 60 seconds

def get_packet_stats() -> PacketStats:
    return packet_stats

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
    app.logger.info(
        f"Responding to {request.method} {request.path} with status {response.status_code}"
    )
    app.logger.debug(f"Response Headers: {dict(response.headers)}")
    return response

# AWS Lambda handler function
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function that processes API Gateway events
    """
    try:
        app.logger.debug(f"Lambda event: {json.dumps(event, indent=2)}")
        app.logger.debug(f"Request context: {json.dumps(event.get('requestContext', {}), indent=2)}")
        app.logger.debug(f"Path parameters: {json.dumps(event.get('pathParameters', {}), indent=2)}")

        # Initialize URLs if needed
        initialize_urls()

        # Add proxy parameter if not present
        path_params = event.get('pathParameters', {})
        if 'proxy' not in path_params:
            path = event.get('path', '')
            if path:
                parts = path.split('/')
                if len(parts) > 2:  # /env/something
                    path_params['proxy'] = '/'.join(parts[2:])
                    event['pathParameters'] = path_params

        # Handle the request using Mangum
        response = handler(event, context)
        app.logger.debug(f"Response: {json.dumps(response, indent=2)}")
        return response
    except Exception as e:
        app.logger.error(f"Lambda handler error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal server error"}),
            "headers": {"Content-Type": "application/json"},
        }

def schedule_url_checks():
    app.logger.info("Setting up URL check schedule")
    # Check all URLs immediately
    for url in urls.values():
        check_url_status(url)
    # Schedule periodic checks
    schedule.every(5).minutes.do(
        lambda: [check_url_status(url) for url in urls.values()]
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port", type=int, default=3001, help="Port to run the server on"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to run the server on"
    )
    parser.add_argument(
        "--no-sniff", action="store_true", default=True, help="Disable packet sniffing"
    )
    args = parser.parse_args()

    # Initialize URLs and start background tasks
    initialize_urls()
    schedule_url_checks()

    # Start packet sniffer in a background thread if enabled
    if not args.no_sniff:
        app.logger.info("Starting packet sniffer thread")
        sniffer_thread = threading.Thread(target=start_packet_sniffer, daemon=True)
        sniffer_thread.start()
    else:
        app.logger.info("Packet sniffing disabled")

    # Start scheduler in a background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    app.run(host=args.host, port=args.port, debug=True)
