"""
AI Infra Monitor - Worker Runner

This script runs the worker loop that processes metrics and creates alerts.
"""

import os
import sys
import time
import asyncio
import logging
import psycopg2
from dotenv import load_dotenv

# Add parent directory to path to import backend modules
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from backend.worker.worker import process_host

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """
    Create a database connection using environment variables.
    
    Returns:
        psycopg2.connection: Database connection object
    """
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    return conn


async def worker_loop():
    """
    Main worker loop that processes all hosts periodically.
    
    Reads configuration from environment:
    - WORKER_INTERVAL: Processing interval in seconds (default: 10)
    """
    interval = int(os.getenv("WORKER_INTERVAL", "10"))
    
    logger.info(f"Worker started with interval: {interval}s")
    
    try:
        while True:
            try:
                # Get database connection
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # Get all host IDs
                cursor.execute("SELECT id FROM hosts ORDER BY id")
                host_ids = [row[0] for row in cursor.fetchall()]
                cursor.close()
                
                if not host_ids:
                    logger.warning("No hosts found in database")
                else:
                    logger.info(f"Processing {len(host_ids)} hosts...")
                    
                    # Process each host
                    for host_id in host_ids:
                        try:
                            alerts = await process_host(host_id, conn)
                            if alerts:
                                logger.info(
                                    f"Host {host_id}: Created {len(alerts)} alerts"
                                )
                        except Exception as e:
                            logger.error(
                                f"Error processing host {host_id}: {e}",
                                exc_info=True
                            )
                
                conn.close()
                
            except psycopg2.Error as e:
                logger.error(f"Database error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
            
            # Sleep until next iteration
            logger.debug(f"Sleeping for {interval}s...")
            await asyncio.sleep(interval)
            
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")


if __name__ == "__main__":
    asyncio.run(worker_loop())
