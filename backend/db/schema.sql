-- AI Infra Monitor Database Schema
-- This script creates the database schema for the AI Infrastructure Monitor

-- Drop tables in correct order (respecting foreign key constraints)
DROP TABLE IF EXISTS analyses CASCADE;
DROP TABLE IF EXISTS alerts CASCADE;
DROP TABLE IF EXISTS process_metrics CASCADE;
DROP TABLE IF EXISTS metrics_raw CASCADE;
DROP TABLE IF EXISTS metrics CASCADE;
DROP TABLE IF EXISTS hosts CASCADE;

-- Create hosts table
CREATE TABLE hosts (
    id SERIAL PRIMARY KEY,
    hostname TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create metrics table
CREATE TABLE metrics (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create metrics_raw table for raw ingest data
CREATE TABLE metrics_raw (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create process_metrics table for process-level monitoring
CREATE TABLE process_metrics (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    process_name TEXT NOT NULL,
    pid INTEGER NOT NULL,
    cpu_percent NUMERIC(5,2),
    memory_mb NUMERIC(10,2),
    status TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create alerts table
CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    metric_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create analyses table
CREATE TABLE analyses (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    alert_id INTEGER REFERENCES alerts(id) ON DELETE CASCADE,
    result JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX idx_metrics_host_id ON metrics(host_id);
CREATE INDEX idx_metrics_created_at ON metrics(created_at);
CREATE INDEX idx_metrics_raw_host_id ON metrics_raw(host_id);
CREATE INDEX idx_metrics_raw_created_at ON metrics_raw(created_at);
CREATE INDEX idx_alerts_host_id ON alerts(host_id);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_analyses_host_id ON analyses(host_id);
CREATE INDEX idx_process_metrics_host_id ON process_metrics(host_id);
CREATE INDEX idx_process_metrics_created_at ON process_metrics(created_at);
CREATE INDEX idx_process_metrics_name ON process_metrics(process_name);

-- Disk Analyzer Tables

-- Create disk_scans table for scan history
CREATE TABLE disk_scans (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, running, completed, failed
    total_size_bytes BIGINT,
    categories JSONB, -- JSON object with categories and their sizes
    recommendations JSONB, -- AI-generated recommendations
    error_message TEXT,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Create cleanup_operations table for cleanup history
CREATE TABLE cleanup_operations (
    id SERIAL PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES disk_scans(id) ON DELETE CASCADE,
    host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, running, completed, failed, rolled_back
    categories_cleaned TEXT[], -- Array of category names that were cleaned
    total_files_deleted INTEGER DEFAULT 0,
    total_size_freed_bytes BIGINT DEFAULT 0,
    backup_path TEXT, -- Path to backup directory
    error_message TEXT,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Create cleanup_items table for individual items to clean
CREATE TABLE cleanup_items (
    id SERIAL PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES disk_scans(id) ON DELETE CASCADE,
    category TEXT NOT NULL, -- temp_files, browser_cache, recycle_bin, duplicates, large_files, etc.
    file_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    last_accessed TIMESTAMP,
    is_safe BOOLEAN DEFAULT true,
    risk_level TEXT DEFAULT 'low', -- low, medium, high
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for disk analyzer tables
CREATE INDEX idx_disk_scans_host_id ON disk_scans(host_id);
CREATE INDEX idx_disk_scans_status ON disk_scans(status);
CREATE INDEX idx_disk_scans_started_at ON disk_scans(started_at);
CREATE INDEX idx_cleanup_operations_scan_id ON cleanup_operations(scan_id);
CREATE INDEX idx_cleanup_operations_host_id ON cleanup_operations(host_id);
CREATE INDEX idx_cleanup_operations_status ON cleanup_operations(status);
CREATE INDEX idx_cleanup_items_scan_id ON cleanup_items(scan_id);
CREATE INDEX idx_cleanup_items_category ON cleanup_items(category);
