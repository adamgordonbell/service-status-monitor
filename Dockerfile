FROM public.ecr.aws/lambda/python:3.11

# Copy requirements file
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install the specified packages
RUN pip install -r requirements.txt

# Copy function code
COPY scripts/ ${LAMBDA_TASK_ROOT}/scripts/
COPY urls_config.toml ${LAMBDA_TASK_ROOT}/

# Set the CMD to your handler
CMD [ "scripts/app_server.lambda_handler" ]
