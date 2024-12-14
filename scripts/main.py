import dagger

async def main():
    # Initialize Dagger client
    async with dagger.Connection() as client:
        # Define source directory
        src = client.host().directory(".", exclude=[".venv", "__pycache__", "*.pyc", "*.pyo", "*.log"])

        # Step 1: Create a container with Python and install dependencies
        python_container = (
            client.container()
            .from_("python:3.11-slim")
            .with_workdir("/app")
            .with_directory("/app", src)  # Copy app files to container
            .with_exec(["pip", "install", "--upgrade", "pip", "setuptools", "wheel"])  # Upgrade pip
            .with_exec(["pip", "install", "."])  # Install app and dependencies from pyproject.toml
        )

        # Step 2: Run the Flask app in the container
        flask_container = (
            python_container
            .with_exposed_port(5000)  # Expose Flask's default port
            .with_exec(["python", "App.py"])  # Run the Flask app
        )

        # Step 3: Publish the container image
        await flask_container.publish("flask-app:latest")  # Publish as a Docker image

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
