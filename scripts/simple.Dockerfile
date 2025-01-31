FROM public.ecr.aws/lambda/python:3.12

# Set up working directory
WORKDIR /app
COPY scripts/simple_server.py scripts/
COPY scripts/simple_entrypoint.sh scripts/

# Install dependencies
RUN pip install --no-cache-dir \
    flask>=3.0.0 \
    mangum>=0.17.0

# Make entrypoint script executable
RUN chmod +x scripts/simple_entrypoint.sh

# Set environment variables
ENV FLASK_APP=scripts/simple_server.py
ENV PYTHONPATH=/app

# Use our entrypoint script
ENTRYPOINT ["/app/scripts/simple_entrypoint.sh"]
