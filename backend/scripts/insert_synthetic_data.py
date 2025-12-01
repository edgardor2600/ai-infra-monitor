"""
Script to insert synthetic CPU data for worker testing

This script inserts synthetic high CPU metrics to trigger worker alerts.
"""

import os
import sys
import psycopg2
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )


def insert_synthetic_data():
    """
    Insert synthetic CPU data to trigger alerts:
    - High CPU values (> 90%) to trigger rule_cpu_over_90
    - Increasing CPU trend to trigger rule_cpu_delta
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ensure we have a host
    cursor.execute(
        "INSERT INTO hosts (hostname) VALUES ('test-host-1') "
        "ON CONFLICT (hostname) DO UPDATE SET hostname = EXCLUDED.hostname "
        "RETURNING id"
    )
    host_id = cursor.fetchone()[0]
    conn.commit()
    
    print(f"Using host_id: {host_id}")
    
    # Insert low CPU values (for 60s average baseline)
    print("Inserting baseline low CPU metrics...")
    for i in range(3):
        payload = {
            "host_id": host_id,
            "timestamp": datetime.utcnow().isoformat(),
            "interval": 5,
            "samples": [
                {"metric": "cpu_percent", "value": 20.0 + i},
                {"metric": "mem_percent", "value": 50.0}
            ]
        }
        
        cursor.execute(
            "INSERT INTO metrics_raw (host_id, payload) VALUES (%s, %s)",
            (host_id, json.dumps(payload))
        )
    
    conn.commit()
    print(f"Inserted 3 baseline metrics")
    
    # Insert high CPU values (for 30s average - will trigger alerts)
    print("Inserting high CPU metrics (will trigger alerts)...")
    for i in range(3):
        payload = {
            "host_id": host_id,
            "timestamp": datetime.utcnow().isoformat(),
            "interval": 5,
            "samples": [
                {"metric": "cpu_percent", "value": 92.0 + i},  # > 90%
                {"metric": "mem_percent", "value": 60.0}
            ]
        }
        
        cursor.execute(
            "INSERT INTO metrics_raw (host_id, payload) VALUES (%s, %s)",
            (host_id, json.dumps(payload))
        )
    
    conn.commit()
    print(f"Inserted 3 high CPU metrics")
    
    # Verify data
    cursor.execute(
        "SELECT COUNT(*) FROM metrics_raw WHERE host_id = %s",
        (host_id,)
    )
    count = cursor.fetchone()[0]
    print(f"\nTotal metrics for host {host_id}: {count}")
    
    cursor.close()
    conn.close()
    
    print("\n✅ Synthetic data inserted successfully!")
    print(f"   Host ID: {host_id}")
    print(f"   Metrics: {count}")
    print("\nNow run the worker:")
    print("   python backend/worker/run_worker.py")


if __name__ == "__main__":
    insert_synthetic_data()
