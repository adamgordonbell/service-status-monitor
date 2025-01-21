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
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response as WerkzeugResponse

class ServiceStatus(TypedDict):
    status: str
    description: str

class ServiceDict(TypedDict):
    services: Dict[str, str]

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

# Check if we should use environment prefixes (default to False for local development)
USE_ENV_PREFIX = os.environ.get('USE_ENV_PREFIX', '').lower() == 'true'

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

class EnvironmentMiddleware:
    def __init__(self, app):
        self.app = app
        self.environments = ENVIRONMENTS

    def __call__(self, environ, start_response):
        # Skip middleware if USE_ENV_PREFIX is False
        if not USE_ENV_PREFIX:
            return self.app(environ, start_response)
            
        path_info = environ.get('PATH_INFO', '')
        app.logger.debug(f"Original path: {path_info}")
        
        # Skip for root path
        if path_info == "/":
            return self.app(environ, start_response)

        # Check if path starts with environment prefix
        for env in self.environments:
            prefix = f"/{env}"
            if path_info.startswith(prefix):
                # Store environment in request context
                environ['service_env'] = env
                # Strip prefix but keep the rest
                new_path = path_info[len(prefix):]
                if not new_path:
                    new_path = "/"
                elif not new_path.startswith("/"):
                    new_path = "/" + new_path
                environ['PATH_INFO'] = new_path
                environ['SCRIPT_NAME'] = prefix
                app.logger.debug(f"Modified path: {new_path}, Environment: {env}")
                return self.app(environ, start_response)

        # No environment prefix found
        response = WerkzeugResponse(
            json.dumps({"message": "Invalid environment"}),
            status=404,
            content_type='application/json'
        )
        return response(environ, start_response)

# Wrap app with environment middleware
app.wsgi_app = EnvironmentMiddleware(app.wsgi_app)

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
        app.logger.debug(f"Path parameters: {json.dumps(event.get('pathParameters', {}), indent=2)}")

        # Initialize URLs if needed
        initialize_urls()

        # Get the path parameters
        path_params = event.get('pathParameters', {})
        if path_params and 'proxy' in path_params:
            app.logger.debug(f"Original proxy path: {path_params['proxy']}")

            # Add environment prefix if USE_ENV_PREFIX is True and path doesn't start with environment
            if USE_ENV_PREFIX:
                path = event['path']
                has_env_prefix = any(path.startswith(f"/{env}") for env in ENVIRONMENTS)
                if not has_env_prefix:
                    # Default to prod environment
                    path = f"/prod{path if path.startswith('/') else '/' + path}"
                    event['path'] = path
                    app.logger.debug(f"Added environment prefix: {path}")

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
