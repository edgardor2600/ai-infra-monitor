"""
Migration script to create scheduled_disk_cleanups table for automated disk maintenance.
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def migrate():
    """Run migration to create scheduled_disk_cleanups table."""
    print("Starting scheduled_disk_cleanups table migration...")
    
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_disk_cleanups (
                id SERIAL PRIMARY KEY,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                org_id INTEGER NOT NULL DEFAULT 1,
                enabled BOOLEAN DEFAULT true,
                categories TEXT[] NOT NULL DEFAULT ARRAY['temp_files', 'browser_cache', 'recycle_bin'],
                interval_hours INTEGER NOT NULL DEFAULT 24,
                last_run_at TIMESTAMP,
                next_run_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """)
        print("✓ Created scheduled_disk_cleanups table")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_cleanups_host ON scheduled_disk_cleanups(host_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_cleanups_next_run ON scheduled_disk_cleanups(next_run_at);")
        print("✓ Created indexes")

        conn.commit()
        cursor.close()
        conn.close()
        print("✓ Scheduled disk cleanups migration completed successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")


if __name__ == "__main__":
    migrate()
