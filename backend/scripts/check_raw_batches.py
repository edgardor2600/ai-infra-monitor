"""
Check recent metrics_raw to see if processes are being sent
"""
import psycopg2
import os
import json
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)

cursor = conn.cursor()

# Get recent batches
print("\n📦 Checking recent metrics_raw batches for process data...\n")

cursor.execute("""
    SELECT id, host_id, payload, created_at 
    FROM metrics_raw 
    ORDER BY created_at DESC 
    LIMIT 10
""")

rows = cursor.fetchall()

for i, row in enumerate(rows, 1):
    batch_id, host_id, payload, created_at = row
    
    # Check if payload has processes
    processes = payload.get('processes', []) if payload else []
    has_processes = processes is not None and len(processes) > 0
    process_count = len(processes) if processes else 0
    
    print(f"{i}. Batch ID: {batch_id}, Host: {host_id}, Time: {created_at}")
    print(f"   Samples: {len(payload.get('samples', []))}")
    print(f"   Processes: {process_count}")
    
    if has_processes and process_count > 0:
        print(f"   ✅ Has process data!")
        print(f"   Sample processes:")
        for proc in payload['processes'][:3]:
            print(f"      - {proc.get('name')} (PID: {proc.get('pid')})")
    else:
        print(f"   ❌ No process data")
    print()

cursor.close()
conn.close()

print("\n💡 If no batches have process data, the agent is not collecting/sending processes.")
print("   This could mean:")
print("   1. The agent hasn't run for 60 seconds yet (process collection interval)")
print("   2. The agent is not running")
print("   3. There's an error in the agent's process collection")
