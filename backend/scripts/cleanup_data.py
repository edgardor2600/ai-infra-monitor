"""
AI Infra Monitor - Data Cleanup Script

This script removes old data from the database to enforce retention policies.
It is designed to be run periodically (e.g., via cron).

Configuration via environment variables:
- RETENTION_DAYS: Number of days to keep data (default: 7)
- DB_*: Database connection parameters
"""

import os
import sys
import logging
import argparse
import psycopg2
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Add parent directory to path to import backend modules if needed
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Create a database connection."""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )


def cleanup_metrics(conn, days: int, dry_run: bool = False) -> int:
    """
    Delete metrics older than the specified number of days.
    
    Args:
        conn: Database connection
        days: Retention period in days
        dry_run: If True, only count rows to be deleted
        
    Returns:
        int: Number of rows deleted (or to be deleted)
    """
    cursor = conn.cursor()
    
    # Calculate cutoff date (UTC)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    logger.info(f"Retention policy: {days} days")
    logger.info(f"Cutoff date: {cutoff_date.isoformat()}")
    
    if dry_run:
        cursor.execute(
            "SELECT COUNT(*) FROM metrics_raw WHERE created_at < %s",
            (cutoff_date,)
        )
        count = cursor.fetchone()[0]
        logger.info(f"[DRY RUN] Would delete {count} rows from metrics_raw")
    else:
        cursor.execute(
            "DELETE FROM metrics_raw WHERE created_at < %s",
            (cutoff_date,)
        )
        count = cursor.rowcount
        conn.commit()
        logger.info(f"Deleted {count} rows from metrics_raw")
        
    cursor.close()
    return count


def main():
    parser = argparse.ArgumentParser(description="Cleanup old data from AI Infra Monitor database")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be deleted without deleting")
    parser.add_argument("--days", type=int, help="Override retention days from env")
    args = parser.parse_args()
    
    # Determine retention days
    days = args.days if args.days is not None else int(os.getenv("RETENTION_DAYS", "7"))
    
    try:
        conn = get_db_connection()
        cleanup_metrics(conn, days, args.dry_run)
        conn.close()
        logger.info("Cleanup completed successfully")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
