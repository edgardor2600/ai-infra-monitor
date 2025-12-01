"""
AI Infra Monitor Agent - CLI Entry Point

Command-line interface for the AI Infra Monitor agent.
Provides commands to run the agent and collect metrics.
"""

import sys
import json
import logging
import click
from agent.collector import collect_once

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
    help="Run in dry-run mode (mock metrics collection)"
)
def run(dry_run: bool):
    """
    Run the agent to collect metrics.
    
    In dry-run mode, the agent collects mock metrics without
    actually querying the system.
    """
    if dry_run:
        logger.info("Running in dry-run mode")
    else:
        logger.info("Running agent")
        logger.warning("Real metrics collection not yet implemented, using mock data")
    
    try:
        # Collect metrics
        metrics = collect_once()
        
        # Output as JSON to stdout
        json_output = json.dumps(metrics, indent=2)
        click.echo(json_output)
        
        logger.info("Metrics collection completed successfully")
        
    except Exception as e:
        logger.error(f"Error collecting metrics: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
