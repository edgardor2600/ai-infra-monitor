import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST'),
    port=os.getenv('DB_PORT')
)

cur = conn.cursor()

# Check total records
cur.execute('SELECT COUNT(*) FROM process_metrics')
total = cur.fetchone()[0]
print(f'Total process_metrics records: {total}')

# Check recent records
cur.execute("SELECT COUNT(*) FROM process_metrics WHERE created_at > NOW() - INTERVAL '10 minutes'")
recent = cur.fetchone()[0]
print(f'Records in last 10 minutes: {recent}')

# Show some sample data
cur.execute("SELECT host_id, process_name, pid, cpu_percent, memory_mb, created_at FROM process_metrics ORDER BY created_at DESC LIMIT 5")
rows = cur.fetchall()
print(f'\nLast 5 records:')
for row in rows:
    print(f'  Host: {row[0]}, Process: {row[1]}, PID: {row[2]}, CPU: {row[3]}%, Memory: {row[4]}MB, Time: {row[5]}')

# Check metrics_raw for processes field
cur.execute("SELECT COUNT(*) FROM metrics_raw WHERE payload::text LIKE '%processes%'")
with_processes = cur.fetchone()[0]
print(f'\nmetrics_raw records with processes field: {with_processes}')

# Show sample metrics_raw with processes
cur.execute("SELECT host_id, payload->'processes', created_at FROM metrics_raw WHERE payload::text LIKE '%processes%' ORDER BY created_at DESC LIMIT 1")
row = cur.fetchone()
if row:
    print(f'\nLast metrics_raw with processes:')
    print(f'  Host: {row[0]}, Processes: {row[1]}, Time: {row[2]}')

cur.close()
conn.close()
