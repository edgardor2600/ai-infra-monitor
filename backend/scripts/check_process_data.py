"""
Quick script to check process_metrics data
"""
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)

cursor = conn.cursor()

# Check total count
cursor.execute("SELECT COUNT(*) FROM process_metrics")
total = cursor.fetchone()[0]
print(f"\n📊 Total process_metrics records: {total}")

# Check recent data (last 5 minutes)
cursor.execute("SELECT COUNT(*) FROM process_metrics WHERE created_at > NOW() - INTERVAL '5 minutes'")
recent_5min = cursor.fetchone()[0]
print(f"📊 Records in last 5 minutes: {recent_5min}")

# Check recent data (last hour)
cursor.execute("SELECT COUNT(*) FROM process_metrics WHERE created_at > NOW() - INTERVAL '1 hour'")
recent_1hour = cursor.fetchone()[0]
print(f"📊 Records in last hour: {recent_1hour}")

# Show most recent records
print(f"\n📋 Most recent 10 records:")
cursor.execute("""
    SELECT process_name, pid, cpu_percent, memory_mb, status, created_at 
    FROM process_metrics 
    ORDER BY created_at DESC 
    LIMIT 10
""")

rows = cursor.fetchall()
for i, row in enumerate(rows, 1):
    name, pid, cpu, mem, status, created = row
    age = datetime.now() - created.replace(tzinfo=None)
    print(f"  {i}. {name:25} PID:{pid:6} CPU:{cpu:5.1f}% MEM:{mem:7.1f}MB [{age}]")

# Check if there are any non-test records
cursor.execute("SELECT COUNT(*) FROM process_metrics WHERE process_name != 'test_process.exe'")
non_test = cursor.fetchone()[0]
print(f"\n📊 Non-test records: {non_test}")

cursor.close()
conn.close()

if recent_5min == 0:
    print("\n⚠️  WARNING: No recent data! The agent might not be sending process metrics.")
    print("   Check the agent logs for:")
    print("   - 'Collected X process metrics'")
    print("   - 'Including X process metrics in batch'")
