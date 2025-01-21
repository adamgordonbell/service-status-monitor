import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
import json
import os

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

# Create an ECR repository
repository = aws.ecr.Repository("app-server-repo",
    force_delete=True,
    image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
        scan_on_push=True,
    )
)

# Build and push the Docker image to ECR
image = awsx.ecr.Image("app-server-image",
    repository_url=repository.repository_url,
    context="..",  
    dockerfile="Dockerfile",
    platform="linux/amd64"
)

# Create a Lambda function
lambda_function = aws.lambda_.Function("custom-lambda",
    name="custom-lambda",
    package_type="Image",
    image_uri=image.image_uri,
    role=lambda_role.arn,
    timeout=30,
    memory_size=512,
    environment={
        "variables": {
            "FLASK_ENV": "production"
        }
    }
)

# Create API Gateway stage
stage = aws.apigatewayv2.Stage("api-stage",
    api_id=api_gateway.id,
    name="$default",
    auto_deploy=True
)

# Attach the Lambda to the API Gateway
api_integration = aws.apigatewayv2.Integration("api-lambda-integration",
    api_id=api_gateway.id,
    integration_type="AWS_PROXY",
    integration_uri=lambda_function.arn,
    integration_method="POST",
    payload_format_version="2.0"
)

# Create routes for prod, candidate, and stable
prod_route = aws.apigatewayv2.Route("prod-route",
    api_id=api_gateway.id,
    route_key="ANY /prod/{proxy+}",
    target=api_integration.id.apply(lambda id: f"integrations/{id}")
)

candidate_route = aws.apigatewayv2.Route("candidate-route",
    api_id=api_gateway.id,
    route_key="ANY /candidate/{proxy+}",
    target=api_integration.id.apply(lambda id: f"integrations/{id}")
)

stable_route = aws.apigatewayv2.Route("stable-route",
    api_id=api_gateway.id,
    route_key="ANY /stable/{proxy+}",
    target=api_integration.id.apply(lambda id: f"integrations/{id}")
)

# Lambda permission for API Gateway
lambda_permission = aws.lambda_.Permission("lambda-permission",
    action="lambda:InvokeFunction",
    function=lambda_function.name,
    principal="apigateway.amazonaws.com",
    source_arn=api_gateway.execution_arn.apply(lambda arn: f"{arn}/*/*")
)

# Export the API URLs for each endpoint
pulumi.export("api_url", api_gateway.api_endpoint)
pulumi.export("prod_url", pulumi.Output.concat(api_gateway.api_endpoint, "/prod"))
pulumi.export("candidate_url", pulumi.Output.concat(api_gateway.api_endpoint, "/candidate"))
pulumi.export("stable_url", pulumi.Output.concat(api_gateway.api_endpoint, "/stable"))

# Export initial version tracking (all same initially)
pulumi.export("prod_version", "initial")
pulumi.export("candidate_version", "initial")
pulumi.export("stable_version", "initial")