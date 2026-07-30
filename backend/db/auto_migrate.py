"""
AI Infra Monitor - Automatic Idempotent Schema Migration
Runs automatically on FastAPI backend startup to guarantee all tables and columns exist in Supabase/PostgreSQL.
"""

import logging
from backend.db.connection import get_db_connection

logger = logging.getLogger(__name__)


def auto_migrate_schema():
    """Ensure all required tables and columns exist in the database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Organizations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                license_tier VARCHAR(50) DEFAULT 'pro_saas',
                webhook_url VARCHAR(500),
                notification_email VARCHAR(255),
                auto_remediation_enabled BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW()
            );
            INSERT INTO organizations (id, name, license_tier)
            VALUES (1, 'Organización Principal', 'pro_saas')
            ON CONFLICT (id) DO NOTHING;
        """)
        
        # 2. Users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE DEFAULT 1,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # 3. Hosts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hosts (
                id SERIAL PRIMARY KEY,
                org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE DEFAULT 1,
                hostname TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            ALTER TABLE hosts DROP CONSTRAINT IF EXISTS hosts_hostname_key;
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'hosts_hostname_org_id_key'
                ) THEN
                    ALTER TABLE hosts ADD CONSTRAINT hosts_hostname_org_id_key UNIQUE (hostname, org_id);
                END IF;
            END $$;
        """)
        
        # 4. Metrics & Raw Metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id SERIAL PRIMARY KEY,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                payload JSONB NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS metrics_raw (
                id SERIAL PRIMARY KEY,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                payload JSONB NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS process_metrics (
                id SERIAL PRIMARY KEY,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                process_name TEXT NOT NULL,
                pid INTEGER NOT NULL,
                cpu_percent NUMERIC(5,2),
                memory_mb NUMERIC(10,2),
                status TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """)
        
        # 5. Alerts (With V2 enriched columns)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL PRIMARY KEY,
                org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE DEFAULT 1,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                metric_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                rule_name VARCHAR(100),
                threshold_value FLOAT,
                actual_value FLOAT,
                occurrences_count INTEGER DEFAULT 1,
                last_seen_at TIMESTAMPTZ DEFAULT NOW(),
                resolved_at TIMESTAMPTZ,
                duration_seconds INTEGER,
                ai_diagnosis TEXT,
                ai_recommendation TEXT,
                acknowledged_by VARCHAR(255),
                acknowledged_at TIMESTAMPTZ,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            
            ALTER TABLE alerts
                ADD COLUMN IF NOT EXISTS rule_name VARCHAR(100),
                ADD COLUMN IF NOT EXISTS threshold_value FLOAT,
                ADD COLUMN IF NOT EXISTS actual_value FLOAT,
                ADD COLUMN IF NOT EXISTS occurrences_count INTEGER DEFAULT 1,
                ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT NOW(),
                ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ,
                ADD COLUMN IF NOT EXISTS duration_seconds INTEGER,
                ADD COLUMN IF NOT EXISTS ai_diagnosis TEXT,
                ADD COLUMN IF NOT EXISTS ai_recommendation TEXT,
                ADD COLUMN IF NOT EXISTS acknowledged_by VARCHAR(255),
                ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMPTZ,
                ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) DEFAULT 1;
        """)
        
        # 6. Incidents
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id SERIAL PRIMARY KEY,
                org_id INTEGER NOT NULL DEFAULT 1 REFERENCES organizations(id) ON DELETE CASCADE,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                severity VARCHAR(10) NOT NULL DEFAULT 'HIGH',
                alert_ids INTEGER[] DEFAULT '{}',
                ai_root_cause TEXT,
                ai_next_steps TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                resolved_at TIMESTAMPTZ
            );
        """)

        # 7. Analyses
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id SERIAL PRIMARY KEY,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                alert_id INTEGER REFERENCES alerts(id) ON DELETE CASCADE,
                result JSONB NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """)

        # 8. Disk Scans & Cleanup Operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS disk_scans (
                id SERIAL PRIMARY KEY,
                org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE DEFAULT 1,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'pending',
                total_size_bytes BIGINT,
                categories JSONB,
                recommendations JSONB,
                error_message TEXT,
                started_at TIMESTAMP NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS cleanup_operations (
                id SERIAL PRIMARY KEY,
                org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE DEFAULT 1,
                scan_id INTEGER NOT NULL REFERENCES disk_scans(id) ON DELETE CASCADE,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'pending',
                categories_cleaned TEXT[],
                total_files_deleted INTEGER DEFAULT 0,
                total_size_freed_bytes BIGINT DEFAULT 0,
                backup_path TEXT,
                error_message TEXT,
                started_at TIMESTAMP NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS cleanup_items (
                id SERIAL PRIMARY KEY,
                scan_id INTEGER NOT NULL REFERENCES disk_scans(id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size_bytes BIGINT NOT NULL,
                last_accessed TIMESTAMP,
                is_safe BOOLEAN DEFAULT true,
                risk_level TEXT DEFAULT 'low',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS cleanup_audit_logs (
                id SERIAL PRIMARY KEY,
                org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE DEFAULT 1,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                user_id INTEGER,
                categories TEXT[],
                files_deleted_count INTEGER DEFAULT 0,
                bytes_freed BIGINT DEFAULT 0,
                backup_path TEXT,
                ai_provider VARCHAR(50),
                ai_analysis_summary TEXT,
                executed_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS cleanup_tasks (
                id SERIAL PRIMARY KEY,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                scan_id INTEGER REFERENCES disk_scans(id) ON DELETE CASCADE,
                task_type VARCHAR(50) NOT NULL,
                payload JSONB NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                result JSONB,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_cleanup_tasks_host_status ON cleanup_tasks(host_id, status);
        """)
        
        # Clean up old phantom test hosts and synthetic metrics so only real agent hosts remain
        try:
            cursor.execute("""
                DELETE FROM hosts 
                WHERE hostname IN ('default-host', 'local-host', 'test-host', 'test-host-1');
            """)
            conn.commit()
        except Exception as cleanup_err:
            logger.warning(f"Phantom host cleanup notice: {cleanup_err}")

        cursor.close()
        logger.info("Auto-migration: All database tables and columns verified successfully.")
    except Exception as e:
        logger.error(f"Auto-migration warning: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
