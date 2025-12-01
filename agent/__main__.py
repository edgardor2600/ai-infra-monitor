"""
AI Infra Monitor Agent - CLI Entry Point

Command-line interface for the AI Infra Monitor agent.
Provides commands to run the agent and collect metrics.
"""

import sys
import asyncio
import logging
import click

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr  # Log to stderr so stdout is clean for JSON output
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0", prog_name="ai-infra-monitor-agent")
def cli():
    """
    AI Infra Monitor Agent
    
    Local monitoring agent for collecting system metrics.
    """
    pass


@cli.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Run in dry-run mode (print batches without sending)"
)
def run(dry_run: bool):
    """
    Run the agent to collect and send metrics.
    
    In dry-run mode, the agent collects metrics and prints batches
    without sending them to the backend.
    
    Configuration via environment variables:
    - AGENT_INTERVAL: Collection interval in seconds (default: 5)
    - AGENT_BATCH_MAX: Maximum samples before flush (default: 20)
    - AGENT_BATCH_TIMEOUT: Maximum seconds before flush (default: 20)
    - BACKEND_URL: Backend server URL (default: http://localhost:8001)
    - AGENT_HOST_ID: Host identifier (default: 1)
    """
    if dry_run:
        logger.info("Running in dry-run mode")
    else:
        logger.info("Running agent")
    
    try:
        # Import here to avoid circular imports
        from agent.run import run as agent_run
        
        # Run the async agent loop
        asyncio.run(agent_run(dry_run=dry_run))
        
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Error running agent: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
