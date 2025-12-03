import psycopg2
import os
import json
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    cursor = conn.cursor()
    
    # Check count
    cursor.execute("SELECT COUNT(*) FROM metrics_raw")
    count = cursor.fetchone()[0]
    print(f"Total metrics_raw records: {count}")
    
    # Check last record
    cursor.execute("SELECT payload, created_at FROM metrics_raw ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        payload, created_at = row
        print(f"Last record at: {created_at}")
        print(f"Payload samples: {json.dumps(payload.get('samples', []), indent=2)}")
    else:
        print("No records found in metrics_raw")
        
    cursor.close()
    conn.close()

except Exception as e:
    print(f"Error: {e}")
