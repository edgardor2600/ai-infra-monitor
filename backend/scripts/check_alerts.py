"""
Simple script to check alerts in database
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
)

cursor = conn.cursor()

# Check alerts
cursor.execute(
    "SELECT id, host_id, metric_name, severity, message, status FROM alerts ORDER BY id"
)
alerts = cursor.fetchall()

print(f"\n✅ Total alerts: {len(alerts)}\n")

for alert in alerts:
    print(f"Alert {alert[0]}:")
    print(f"  Host ID: {alert[1]}")
    print(f"  Metric: {alert[2]}")
    print(f"  Severity: {alert[3]}")
    print(f"  Status: {alert[5]}")
    print(f"  Message: {alert[4]}")
    print()

cursor.close()
conn.close()
