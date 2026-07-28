import os, psycopg2
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(
    dbname='ai_infra_monitor', user='postgres',
    password=os.getenv('DB_PASSWORD','123'), host='localhost', port='5432'
)
cur = conn.cursor()

# Test the exact query executed by get_process_history for host 82
cur.execute("""
    SELECT
        created_at,
        p->>'name' as process_name,
        (p->>'pid')::int as pid,
        (p->>'cpu_percent')::float as cpu_percent,
        (p->>'memory_mb')::float as memory_mb,
        p->>'status' as status
    FROM metrics_raw,
         jsonb_array_elements(payload->'processes') as p
    WHERE host_id = 82
      AND LOWER(p->>'name') = LOWER('python.exe')
      AND created_at >= NOW() - (1 || ' hours')::INTERVAL
    ORDER BY created_at ASC
""")
rows = cur.fetchall()
print('Strategy 1 (1 hour) rows:', len(rows))

if not rows:
    cur.execute("""
        SELECT
            created_at,
            p->>'name' as process_name,
            (p->>'pid')::int as pid,
            (p->>'cpu_percent')::float as cpu_percent,
            (p->>'memory_mb')::float as memory_mb,
            p->>'status' as status
        FROM metrics_raw,
             jsonb_array_elements(payload->'processes') as p
        WHERE host_id = 82
          AND LOWER(p->>'name') = LOWER('python.exe')
        ORDER BY created_at DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    rows.reverse()
    print('Fallback 1a (most recent) rows:', len(rows))

print('Returned history samples:', len(rows))
if rows:
    print('First sample:', rows[0])
    print('Last sample:', rows[-1])

conn.close()
