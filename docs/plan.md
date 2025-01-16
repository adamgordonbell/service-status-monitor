## Planning docs:

- https://claude.ai/chat/6c0e5197-60f9-4d3f-a548-8f5568647f1c
- https://chatgpt.com/c/67895540-8994-800f-92b9-f0331e23d51c

## High Level Objective
Demonstrate modern Python CLI development patterns by building a practical DevOps tool. We'll implement Lambda rolling updates using Pulumi's Automation API, showing how different Python CLI frameworks handle real-world requirements like interactive prompts and progress display. This provides concrete examples of when to choose different frameworks while teaching practical infrastructure automation.

## Current Project Status
The project is a DevOps demonstration combining several modern tools and practices:

### Core Components
- Web Application + CLI tool deployed to AWS
- Infrastructure managed with Pulumi (Python)
- Helper scripts in `util/functions` for common operations
- Flask-based web application with Hypercorn server
- Rich-powered CLI dashboard
- AWS Lambda/API Gateway integration via Mangum

### Infrastructure & Deployment
- Pulumi stack management
- AWS Lambda deployment pipeline
- API Gateway integration
- Environment setup through initialization function

### Development Tools
- UV for Python dependency management
- Pytest for testing
- Rich for CLI formatting
- Container support (Dockerfile pending Dagger migration)

## Rolling Updates Implementation Plan

### Infrastructure Setup
API Gateway (auto-generated URL) with three endpoints:
- `/prod` - Production endpoint (handles traffic shifting)
- `/candidate` - New version being tested
- `/stable` - Last known-good version for rollback

### Version Tracking
- Using git hashes instead of version numbers
- Stack outputs store:
  - Current hash in prod
  - Current hash in candidate (if any)
  - Current hash in stable
  - API Gateway URLs for each endpoint

### Key Workflows
1. Deploy New Version
```bash
pulumi-tool deploy
# Gets current git HEAD
# Deploys to candidate endpoint
```

2. Progressive Rollout
```bash
pulumi-tool rollout
# Start traffic shifting
# Press any key to abort
# If successful, promote to stable
```

3. Rollback
```bash
pulumi-tool rollback
# Immediate restore to stable version
```

### RollingDeployer Class
Core automation logic shared across CLI implementations:
```python
class RollingDeployer:
    async def get_status()  # Show current prod/candidate/stable hashes
    async def deploy_candidate()  # Deploy current git HEAD to candidate
    async def start_rollout()  # Start traffic shift, return True if completed
    async def rollback_to_stable()  # Immediate switch to stable
```

### CLI Framework Progression
Implementation order with key features to demonstrate:

1. argparse + questionary
   - Baseline implementation
   - Adding interactive features to standard library

2. Click
   - Traditional decorator pattern
   - Built-in interactive support

3. Typer
   - Modern Python type hints
   - Click compatibility

4. (Optional) Additional frameworks to consider:
   - cyclopts (type-safe)
   - Cliff (enterprise-grade)

## Open Questions

### Technical Implementation
1. Traffic Shifting
   - How exactly do we implement traffic shifting in API Gateway?
   - What APIs/methods are available?
   - Do we need additional AWS resources?

2. Git Integration
   - Best way to get current git hash?
   - Should we validate git state (clean working directory)?
   - Handle tags vs hashes?

3. State Management
   - What happens if deployment fails midway?
   - How to handle concurrent deployments?
   - State recovery procedures?

### Article Structure
1. Framework Comparison
   - How to structure the comparison fairly?
   - What metrics to compare?
   - How much code to show vs explain?

2. Pulumi Teaching
   - How much Pulumi knowledge to assume?
   - Balance between CLI and infrastructure concepts?
   - What automation API concepts to highlight?

## Next Steps
1. Implement basic Pulumi stack with three endpoints
2. Build RollingDeployer class
3. Create argparse + questionary implementation
4. Research traffic shifting implementation
5. Add remaining CLI framework implementations
6. Write article comparing approaches

## Success Criteria
1. Working rolling update implementation
2. Clear comparison of CLI frameworks
3. Practical value for Python developers
4. Demonstrates Pulumi Automation API benefits
5. Publishable tutorial/article