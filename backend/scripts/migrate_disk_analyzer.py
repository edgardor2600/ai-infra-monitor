"""
Migration script to add disk analyzer tables.

This script adds the disk_scans, cleanup_operations, and cleanup_items tables
to the existing database.
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def migrate():
    """Run the migration"""
    print("Starting disk analyzer tables migration...")
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        
        cursor = conn.cursor()
        
        # Read and execute schema
        print("Creating disk analyzer tables...")
        
        # Create disk_scans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS disk_scans (
                id SERIAL PRIMARY KEY,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'pending',
                total_size_bytes BIGINT,
                categories JSONB,
                recommendations JSONB,
                error_message TEXT,
                started_at TIMESTAMP NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMP
            );
        """)
        print("✓ Created disk_scans table")
        
        # Create cleanup_operations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cleanup_operations (
                id SERIAL PRIMARY KEY,
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
        """)
        print("✓ Created cleanup_operations table")
        
        # Create cleanup_items table
        cursor.execute("""
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
        """)
        print("✓ Created cleanup_items table")
        
        # Create indexes
        print("Creating indexes...")
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_disk_scans_host_id ON disk_scans(host_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_disk_scans_status ON disk_scans(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_disk_scans_started_at ON disk_scans(started_at);")
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cleanup_operations_scan_id ON cleanup_operations(scan_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cleanup_operations_host_id ON cleanup_operations(host_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cleanup_operations_status ON cleanup_operations(status);")
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cleanup_items_scan_id ON cleanup_items(scan_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cleanup_items_category ON cleanup_items(category);")
        
        print("✓ Created indexes")
        
        # Commit changes
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n✅ Migration completed successfully!")
        print("\nNew tables created:")
        print("  - disk_scans")
        print("  - cleanup_operations")
        print("  - cleanup_items")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    migrate()
