# Python DevOps Demonstration Project

## Infrastructure and DevOps Overview

This project serves as a little demonstration of DevOps practices using Python. It showcases the integration of several  tools and libraries to create a Web and CLI tool and deploy it to AWS using Pulumi .

### Key Technologies

- **Infrastructure as Code**: Using `Pulumi` with Python for AWS infrastructure management
- **Container Orchestration**: Primarily utilizing `Dagger` for container workflows and CI/CD
- **Core Libraries and Tools**:
  - `pulumi` & `pulumi-aws`: For infrastructure as code
  - `dagger-io`: Modern CI/CD and container workflows
  - `flask`: Web application framework
  - `hypercorn`: ASGI web server
  - `pytest` & `pytest-cov`: Testing and coverage
  - `rich`: Rich text and beautiful formatting for CLI
  - `mangum`: AWS Lambda/API Gateway integration
  - Additional utilities: `redis`, `flask-rq2`, `schedule`

### Helper Scripts

The project includes a set of convenient helper scripts in the `util/functions` file. These include:

- `,run_app_server`: Start the Flask application server with sudo privileges
- `,run_no_sniff`: Run the app without packet sniffing (no sudo required)
- `,run_cli`: Launch the CLI dashboard
- `,run_tests`: Execute the test suite
- `,pulumi_up`: Deploy infrastructure changes using Pulumi
- `,run_check_api`: Test the lambda endpoint

To use these helpers, source the functions file from the repository root and run the desired command.

The idea is to demonstrate modern DevOps practices including infrastructure as code, containerization, and automated testing, all implemented in Python, in a small amount of code.

The Dockerfile is the one exception, I still need to port it to Dagger.
