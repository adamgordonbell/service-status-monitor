#!/bin/bash

if [ "$RUN_MODE" = "local" ]; then
    echo "Starting in local mode..."
    exec python scripts/simple_server.py
else
    echo "Starting in Lambda mode..."
    exec python -m awslambdaric scripts.simple_server.lambda_handler
fi
