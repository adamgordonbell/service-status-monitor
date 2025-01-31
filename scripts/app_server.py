from flask import Flask, render_template, jsonify, request, Response
import requests
import schedule
import time
import threading
import logging
import argparse
from typing import Dict, Any, TypedDict, NoReturn
import json
from mangum import Mangum
import os
from asgiref.wsgi import WsgiToAsgi
import toml
from werkzeug.wrappers import Response as WerkzeugResponse

class ServiceStatus(TypedDict):
    status: str
    description: str

class ServiceDict(TypedDict):
    services: Dict[str, str]

class PrefixStripper:
    """WSGI middleware to strip '/prod' or '/candidate' or '/stable' from PATH_INFO."""
    def __init__(self, app, valid_prefixes=("prod", "candidate", "stable")):
        self.app = app
        self.valid_prefixes = valid_prefixes

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        # Check if path starts with e.g. /prod
        for prefix in self.valid_prefixes:
            candidate = f"/{prefix}"
            if path.startswith(candidate):
                # Remove the prefix from PATH_INFO
                environ['PATH_INFO'] = path[len(candidate):] or '/'
                break
        return self.app(environ, start_response)

# Create Flask app
app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app.logger.setLevel(logging.DEBUG)

# Add prefix stripping middleware
app.wsgi_app = PrefixStripper(app.wsgi_app)

@app.route('/', methods=['GET'])
def root():
    try:
        return render_template('index.html')
    except Exception as e:
        app.logger.error(f"Error rendering template: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

@app.route('/status', methods=['GET'])
def status():
    try:
        app.logger.debug(f"Status endpoint called, returning: {statuses}")
        return jsonify(statuses)
    except Exception as e:
        app.logger.error(f"Error getting status: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

# Convert Flask app to ASGI
asgi_app = WsgiToAsgi(app)

# Configure Mangum handler
handler = Mangum(asgi_app, lifespan="off")

# Load URLs from TOML
def load_urls_from_toml(file_path: str) -> Dict[str, str]:
    try:
        if os.path.exists(file_path):
            return dict(toml.load(file_path).get("urls", {}))
        app.logger.warning(f"Config file {file_path} not found, using default URLs")
        return {
            "github": "https://www.githubstatus.com/api/v2/status.json",
            "openai": "https://status.openai.com/api/v2/summary.json",
            "aws": "https://status.aws.amazon.com/",
        }
    except Exception as e:
        app.logger.error(f"Error loading URLs: {str(e)}")
        return {}

# Initialize empty URLs dict
urls: Dict[str, str] = {}
statuses: Dict[str, ServiceStatus] = {}

def initialize_urls() -> None:
    """Initialize URLs from config file if not already loaded"""
    global urls, statuses
    if not urls:
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "config", "urls.toml"
        )
        urls = load_urls_from_toml(config_path)
        # Initialize statuses for all URLs
        statuses = {
            url: {"status": "unknown", "description": "Checking..."}
            for url in urls.values()
        }
        # Check all URLs immediately
        for url in urls.values():
            check_url_status(url)

# Function to Check URL Status
def check_url_status(url: str) -> None:
    try:
        response = requests.get(url, timeout=5)
        if response.ok:
            statuses[url] = {
                "status": "healthy",
                "description": "Service is responding normally",
            }
        else:
            statuses[url] = {
                "status": "unhealthy",
                "description": f"Service returned status code {response.status_code}",
            }
    except Exception as e:
        statuses[url] = {"status": "critical", "description": str(e)}

# Scheduler Runner
def run_scheduler() -> NoReturn:
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.before_request
def log_request_info() -> None:
    app.logger.info(f"Received {request.method} request to path: {request.path}")
    app.logger.debug(f"Request Headers: {dict(request.headers)}")
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

        # Initialize URLs if needed
        initialize_urls()

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
    # Schedule periodic checks
    schedule.every(5).minutes.do(
        lambda: [check_url_status(url) for url in urls.values()]
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port", type=int, default=3000, help="Port to run the server on"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to run the server on"
    )

    args = parser.parse_args()

    # Initialize URLs
    initialize_urls()

    # Schedule URL checks
    schedule_url_checks()

    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    app.run(host=args.host, port=args.port, debug=True)
