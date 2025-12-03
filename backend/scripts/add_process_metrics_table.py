"""
Migration script to add process_metrics table to the database.

This script adds the process_metrics table for monitoring individual processes.
It can be run safely multiple times (idempotent).
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def run_migration():
    """Run the migration to add process_metrics table."""
    
    # Connect to database
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    
    cursor = conn.cursor()
    
    try:
        print("Creating process_metrics table...")
        
        # Create table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS process_metrics (
                id SERIAL PRIMARY KEY,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                process_name TEXT NOT NULL,
                pid INTEGER NOT NULL,
                cpu_percent NUMERIC(5,2),
                memory_mb NUMERIC(10,2),
                status TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_process_metrics_host_id 
            ON process_metrics(host_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_process_metrics_created_at 
            ON process_metrics(created_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_process_metrics_name 
            ON process_metrics(process_name)
        """)
        
        conn.commit()
        print("✓ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_migration()
