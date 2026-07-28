-- AI Infra Monitor Complete Production Schema for Supabase / PostgreSQL
-- Run this script in the Supabase SQL Editor to initialize all tables and indexes.

-- 1. Create Organizations table (Multi-tenant SaaS)
CREATE TABLE IF NOT EXISTS organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    license_tier VARCHAR(50) DEFAULT 'pro_saas',
    webhook_url VARCHAR(500),
    notification_email VARCHAR(255),
    auto_remediation_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert Default Main Organization if not exists
INSERT INTO organizations (id, name, license_tier)
VALUES (1, 'Organización Principal', 'pro_saas')
ON CONFLICT (id) DO NOTHING;

-- 2. Create Users table (Authentication)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE DEFAULT 1,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. Create Hosts table
CREATE TABLE IF NOT EXISTS hosts (
    id SERIAL PRIMARY KEY,
    org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE DEFAULT 1,
    hostname TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Insert Default Host for initial telemetry fallback
INSERT INTO hosts (id, hostname)
VALUES (1, 'default-host')
ON CONFLICT (id) DO NOTHING;

-- 4. Create Metrics table
CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 5. Create Metrics Raw table
CREATE TABLE IF NOT EXISTS metrics_raw (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 6. Create Process Metrics table
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

-- 7. Create Alerts table (Enriched V2 Schema)
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

-- Ensure all V2 columns exist on pre-existing tables
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

-- 8. Create Incidents table
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

-- 9. Create Analyses table (AI Analysis results)
CREATE TABLE IF NOT EXISTS analyses (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    alert_id INTEGER REFERENCES alerts(id) ON DELETE CASCADE,
    result JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 10. Create Disk Scans table
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

-- 11. Create Cleanup Operations table
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

-- 12. Create Cleanup Items table
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

-- 13. Create Cleanup Audit Logs table
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

-- Create Indexes for fast querying
CREATE INDEX IF NOT EXISTS idx_metrics_host_id ON metrics(host_id);
CREATE INDEX IF NOT EXISTS idx_metrics_created_at ON metrics(created_at);
CREATE INDEX IF NOT EXISTS idx_metrics_raw_host_id ON metrics_raw(host_id);
CREATE INDEX IF NOT EXISTS idx_metrics_raw_created_at ON metrics_raw(created_at);
CREATE INDEX IF NOT EXISTS idx_process_metrics_host_id ON process_metrics(host_id);
CREATE INDEX IF NOT EXISTS idx_process_metrics_created_at ON process_metrics(created_at);
CREATE INDEX IF NOT EXISTS idx_process_metrics_name ON process_metrics(process_name);

CREATE INDEX IF NOT EXISTS idx_alerts_host_id ON alerts(host_id);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_rule_name ON alerts(rule_name);
CREATE INDEX IF NOT EXISTS idx_analyses_host_id ON analyses(host_id);

CREATE INDEX IF NOT EXISTS idx_disk_scans_host_id ON disk_scans(host_id);
CREATE INDEX IF NOT EXISTS idx_disk_scans_status ON disk_scans(status);
CREATE INDEX IF NOT EXISTS idx_disk_scans_started_at ON disk_scans(started_at);

CREATE INDEX IF NOT EXISTS idx_cleanup_operations_scan_id ON cleanup_operations(scan_id);
CREATE INDEX IF NOT EXISTS idx_cleanup_operations_host_id ON cleanup_operations(host_id);
CREATE INDEX IF NOT EXISTS idx_cleanup_operations_status ON cleanup_operations(status);

CREATE INDEX IF NOT EXISTS idx_cleanup_items_scan_id ON cleanup_items(scan_id);
CREATE INDEX IF NOT EXISTS idx_cleanup_items_category ON cleanup_items(category);

-- Reset Sequences to ensure SERIAL IDs start above pre-inserted default records
SELECT setval('organizations_id_seq', (SELECT MAX(id) FROM organizations));
SELECT setval('hosts_id_seq', (SELECT MAX(id) FROM hosts));
