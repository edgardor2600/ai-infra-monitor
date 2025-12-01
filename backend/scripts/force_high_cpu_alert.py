"""
Script to insert ONLY high CPU data to trigger alerts
"""

import os
import sys
import json
import psycopg2
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add parent directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

def insert_high_cpu_only(host_id=1):
    """Insert ONLY high CPU metrics to guarantee alert trigger"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        print(f"Inserting HIGH CPU metrics for host {host_id}...")
        
        # Insert 10 samples of very high CPU (95-98%)
        for i in range(10):
            payload = {
                "host_id": host_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "interval": 5,
                "samples": [
                    {"metric": "cpu_percent", "value": 95.0 + (i * 0.3)},
                    {"metric": "mem_percent", "value": 75.0}
                ]
            }
            
            cursor.execute(
                "INSERT INTO metrics_raw (host_id, payload) VALUES (%s, %s::jsonb)",
                (host_id, json.dumps(payload))
            )
        
        conn.commit()
        print(f"✅ Inserted 10 HIGH CPU samples (95-98%)")
        print(f"   Wait 10-15 seconds for the worker to process...")
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    insert_high_cpu_only()
