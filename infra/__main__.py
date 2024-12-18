import pulumi
import pulumi_aws as aws
import json
import os
import shutil
import subprocess

print("here we are")

user_input = input("Enter your name: ")
print(f"Hello {user_input}!")

# Ensure the deployment directory exists and is clean
if os.path.exists("deployment"):
    shutil.rmtree("deployment")
os.makedirs("deployment")

# Copy the app server file
shutil.copy("../scripts/app_server.py", "deployment/app.py")

# Create the Lambda handler file
with open("deployment/lambda_handler.py", "w") as f:
    f.write('''
import json
from app import app
from awsgi import wsgi

def handler(event, context):
    return wsgi.response(app, event, context)
''')

# Create requirements.txt for Lambda
with open("deployment/requirements.txt", "w") as f:
    f.write('''flask==2.3.3
aws-wsgi==0.2.7''')

# Install dependencies
subprocess.run([
    "pip",
    "install",
    "-r", "deployment/requirements.txt",
    "-t", "deployment/"
], check=True)

# Create the Lambda asset
asset = pulumi.AssetArchive({
    ".": pulumi.FileArchive("./deployment")
})

# Create an API Gateway
api_gateway = aws.apigatewayv2.Api("custom-api",
    name="CustomAPI",
    protocol_type="HTTP",
    route_selection_expression="$request.method $request.path"
)

# Create IAM role for Lambda
lambda_role = aws.iam.Role("lambda-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Effect": "Allow",
            "Sid": ""
        }]
    })
)

# Attach basic Lambda execution policy
lambda_role_policy = aws.iam.RolePolicyAttachment("lambda-role-policy",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
)

# Create a Lambda function
lambda_function = aws.lambda_.Function("custom-lambda",
    name="custom-lambda",
    runtime="python3.9",
    handler="lambda_handler.handler",
    role=lambda_role.arn,  # Use the newly created role
    code=asset,
    timeout=30,
    memory_size=512,
    environment={
        "variables": {
            "FLASK_ENV": "production"
        }
    }
)

# Attach the Lambda to the API Gateway
api_integration = aws.apigatewayv2.Integration("api-lambda-integration",
    api_id=api_gateway.id,
    integration_type="AWS_PROXY",
    integration_uri=lambda_function.arn,
    integration_method="POST",
    payload_format_version="2.0"
)

# Define a route for the API
api_route = aws.apigatewayv2.Route("api-route",
    api_id=api_gateway.id,
    route_key="ANY /{proxy+}",
    target=api_integration.id.apply(lambda id: f"integrations/{id}")
)

# Create a default route for the root path
root_route = aws.apigatewayv2.Route("root-route",
    api_id=api_gateway.id,
    route_key="ANY /",
    target=api_integration.id.apply(lambda id: f"integrations/{id}")
)

# Create a stage for the API
api_stage = aws.apigatewayv2.Stage("api-stage",
    api_id=api_gateway.id,
    name="default",
    auto_deploy=True
)

# Lambda permission for API Gateway
lambda_permission = aws.lambda_.Permission("lambda-permission",
    action="lambda:InvokeFunction",
    function=lambda_function.name,
    principal="apigateway.amazonaws.com",
    source_arn=api_gateway.execution_arn.apply(lambda arn: f"{arn}/*/*")
)

# Export the API URL
pulumi.export("api_url", api_gateway.api_endpoint)