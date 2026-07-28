"""
AI Infra Monitor — Alert System v2 Migration Script

Adds enriched columns to alerts table and creates the incidents table
for intelligent alert grouping. Fully idempotent — safe to run multiple times.

Usage:
    python backend/scripts/migrate_alerts_v2.py
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "123"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )


ALERTS_MIGRATION_SQL = """
-- ───────────────────────────────────────────────────────────────
-- STEP 1: Extend alerts table with intelligence columns
-- ───────────────────────────────────────────────────────────────
ALTER TABLE alerts
    ADD COLUMN IF NOT EXISTS rule_name          VARCHAR(100),
    ADD COLUMN IF NOT EXISTS threshold_value    FLOAT,
    ADD COLUMN IF NOT EXISTS actual_value       FLOAT,
    ADD COLUMN IF NOT EXISTS occurrences_count  INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS last_seen_at       TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS resolved_at        TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS duration_seconds   INTEGER,
    ADD COLUMN IF NOT EXISTS ai_diagnosis       TEXT,
    ADD COLUMN IF NOT EXISTS ai_recommendation  TEXT,
    ADD COLUMN IF NOT EXISTS acknowledged_by    VARCHAR(255),
    ADD COLUMN IF NOT EXISTS acknowledged_at    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS org_id             INTEGER;

-- ───────────────────────────────────────────────────────────────
-- STEP 2: Create incidents table for correlated alert grouping
-- ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS incidents (
    id                  SERIAL PRIMARY KEY,
    org_id              INTEGER NOT NULL,
    host_id             INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    title               VARCHAR(255) NOT NULL,
    status              VARCHAR(20)  NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open', 'acknowledged', 'resolved')),
    severity            VARCHAR(10)  NOT NULL DEFAULT 'HIGH'
                            CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO')),
    alert_ids           INTEGER[]    DEFAULT '{}',
    ai_root_cause       TEXT,
    ai_action_plan      TEXT,
    acknowledged_by     VARCHAR(255),
    acknowledged_at     TIMESTAMPTZ,
    resolved_at         TIMESTAMPTZ,
    duration_seconds    INTEGER,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ───────────────────────────────────────────────────────────────
-- STEP 3: Performance indexes
-- ───────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_alerts_host_rule_status
    ON alerts (host_id, rule_name, status);

CREATE INDEX IF NOT EXISTS idx_alerts_org_created
    ON alerts (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_status_last_seen
    ON alerts (status, last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_incidents_org_status
    ON incidents (org_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_incidents_host
    ON incidents (host_id, created_at DESC);

-- ───────────────────────────────────────────────────────────────
-- STEP 4: Backfill existing alerts with defaults
-- ───────────────────────────────────────────────────────────────
UPDATE alerts
SET
    last_seen_at      = COALESCE(last_seen_at, created_at),
    occurrences_count = COALESCE(occurrences_count, 1)
WHERE last_seen_at IS NULL OR occurrences_count IS NULL;
"""


def run_migration():
    print("🚀 AI Infra Monitor — Alert System v2 Migration")
    print("=" * 55)

    try:
        conn = get_db_connection()
        print("✅ Connected to PostgreSQL")
    except Exception as e:
        print(f"❌ Cannot connect to database: {e}")
        sys.exit(1)

    try:
        cursor = conn.cursor()
        cursor.execute(ALERTS_MIGRATION_SQL)
        conn.commit()
        print("✅ alerts table extended with intelligence columns")
        print("✅ incidents table created")
        print("✅ Performance indexes applied")
        print("✅ Existing rows backfilled with defaults")

        # Verify
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'alerts'
              AND column_name IN (
                'rule_name','occurrences_count','last_seen_at',
                'resolved_at','ai_diagnosis','ai_recommendation',
                'duration_seconds','actual_value','threshold_value'
              )
            ORDER BY column_name;
        """)
        cols = [r[0] for r in cursor.fetchall()]
        print(f"\n📋 Verified alert columns: {', '.join(cols)}")

        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'incidents'
            );
        """)
        exists = cursor.fetchone()[0]
        print(f"📋 incidents table exists: {'✅ YES' if exists else '❌ NO'}")

        cursor.close()
        conn.close()
        print("\n🎉 Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        conn.close()
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
