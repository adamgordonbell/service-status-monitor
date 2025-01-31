#!/bin/bash

if [ "$RUN_MODE" = "local" ]; then
    echo "Starting in local mode..."
    exec python scripts/app_server.py --host 0.0.0.0 --port 3000
else
    echo "Starting in Lambda mode..."
    exec python -m awslambdaric scripts.app_server.lambda_handler
fi
