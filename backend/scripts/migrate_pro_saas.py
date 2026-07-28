"""
Migration script for Pro SaaS Edition.
Adds multi-tenant support (organizations, users, roles, audit logs) and org_id columns.
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def migrate_pro():
    print("Starting Pro SaaS Edition database migration...")
    
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    cursor = conn.cursor()
    
    # 1. Create organizations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            license_tier VARCHAR(50) DEFAULT 'pro',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    print("✓ Created organizations table")
    
    # Insert default organization if missing
    cursor.execute("SELECT id FROM organizations WHERE id = 1;")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO organizations (id, name, license_tier) VALUES (1, 'Organización Principal', 'pro_saas');")
        print("✓ Created default organization (ID: 1)")

    # 2. Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(50) DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    print("✓ Created users table")
    
    # 3. Create cleanup_audit_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cleanup_audit_logs (
            id SERIAL PRIMARY KEY,
            org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
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
    """)
    print("✓ Created cleanup_audit_logs table")
    
    # 4. Add org_id to existing tables if missing
    tables = ['hosts', 'disk_scans', 'cleanup_operations', 'alerts']
    for table in tables:
        cursor.execute(f"""
            ALTER TABLE {table} 
            ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) DEFAULT 1;
        """)
        print(f"✓ Added org_id to table {table}")

    # 5. Add notification and auto-remediation columns to organizations
    cursor.execute("""
        ALTER TABLE organizations
        ADD COLUMN IF NOT EXISTS webhook_url VARCHAR(500),
        ADD COLUMN IF NOT EXISTS notification_email VARCHAR(255),
        ADD COLUMN IF NOT EXISTS auto_remediation_enabled BOOLEAN DEFAULT true;
    """)
    print("✓ Added webhook_url, notification_email, auto_remediation_enabled to organizations table")
        
    conn.commit()
    cursor.close()
    conn.close()
    print("\n✅ Pro SaaS Migration completed successfully!")


if __name__ == "__main__":
    migrate_pro()
