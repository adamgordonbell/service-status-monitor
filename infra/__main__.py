import pulumi
import pulumi_aws as aws

# Define the custom domain name
custom_domain_name = "insertdomainname.com"

# ACM Certificate for the custom domain
acm_cert = aws.acm.Certificate("custom-domain-cert",
    domain_name=custom_domain_name,
    validation_method="DNS"
)

# Create an API Gateway
api_gateway = aws.apigatewayv2.Api("custom-api",
    name="CustomAPI",
    protocol_type="HTTP",
    route_selection_expression="$request.method $request.path"
)

# Create a Lambda function from a container image
lambda_function = aws.lambda_.Function("custom-lambda",
    function_name="custom-lambda",
    image_uri="459018586415.dkr.ecr.us-east-1.amazonaws.com/lambda-api:latest",
    package_type="Image",
    memory_size=512,
    timeout=30,
    role="arn:aws:iam::459018586415:role/service-role/lambda-api-role",
    environment={
        "variables": {
            "EXAMPLE_ENV_VAR": "value"
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
    target=f"integrations/{api_integration.id}"
)

# Create a stage for the API
api_stage = aws.apigatewayv2.Stage("api-stage",
    api_id=api_gateway.id,
    name="default",
    auto_deploy=True
)

# Custom domain for the API Gateway
api_domain = aws.apigatewayv2.DomainName("api-domain",
    domain_name=custom_domain_name,
    domain_name_configuration={
        "certificate_arn": acm_cert.arn,
        "endpoint_type": "REGIONAL"
    }
)

# Map the custom domain to the API
api_mapping = aws.apigatewayv2.ApiMapping("api-mapping",
    api_id=api_gateway.id,
    domain_name=api_domain.id,
    stage=api_stage.id
)

# Lambda permission for API Gateway
lambda_permission = aws.lambda_.Permission("lambda-permission",
    action="lambda:InvokeFunction",
    function=lambda_function.name,
    principal="apigateway.amazonaws.com",
    source_arn=f"{api_gateway.execution_arn}/*/*"
)

# Export the API URL
pulumi.export("api_url", api_gateway.api_endpoint)
pulumi.export("custom_domain_name", custom_domain_name)