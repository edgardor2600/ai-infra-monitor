"""
Database Initialization Script

This script initializes the AI Infra Monitor database by:
1. Reading connection parameters from environment variables
2. Connecting to PostgreSQL
3. Executing the schema.sql file
4. Creating all necessary tables
"""

import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_db_connection():
    """
    Create a database connection using environment variables.
    
    Returns:
        psycopg2.connection: Database connection object
    
    Raises:
        Exception: If connection fails
    """
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        return conn
    except psycopg2.Error as e:
        print(f"❌ Error connecting to database: {e}")
        raise


def load_schema_file():
    """
    Load the schema.sql file content.
    
    Returns:
        str: SQL schema content
    
    Raises:
        FileNotFoundError: If schema.sql doesn't exist
    """
    # Get the path to schema.sql relative to this script
    script_dir = Path(__file__).parent
    schema_path = script_dir.parent / "db" / "schema.sql"
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        return f.read()


def init_database():
    """
    Initialize the database by executing the schema.sql file.
    """
    print("🔧 Initializing AI Infra Monitor database...")
    print()
    
    # Load schema
    try:
        schema_sql = load_schema_file()
        print("✅ Schema file loaded successfully")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # Connect to database
    try:
        conn = get_db_connection()
        print(f"✅ Connected to database: {os.getenv('DB_NAME', 'ai_infra_monitor')}")
    except Exception:
        sys.exit(1)
    
    # Execute schema
    try:
        cursor = conn.cursor()
        cursor.execute(schema_sql)
        conn.commit()
        print("✅ Schema executed successfully")
        
        # Verify tables were created
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        print()
        print("📋 Created tables:")
        for table in tables:
            print(f"   - {table[0]}")
        
        # Verify metrics table is empty
        cursor.execute("SELECT count(*) FROM metrics;")
        count = cursor.fetchone()[0]
        print()
        print(f"✅ Metrics table initialized (count: {count})")
        
        cursor.close()
        
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error executing schema: {e}")
        sys.exit(1)
    finally:
        conn.close()
        print()
        print("✅ Database connection closed")
    
    print()
    print("🎉 Database initialization completed successfully!")


if __name__ == "__main__":
    init_database()
