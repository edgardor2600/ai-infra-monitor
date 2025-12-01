"""
Script to update database schema for Sprint 4
Adds alert_id column to analyses table
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def update_schema():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='analyses' AND column_name='alert_id'
        """)
        
        if cursor.fetchone():
            print("✓ Column 'alert_id' already exists in analyses table")
        else:
            # Add the column
            cursor.execute("""
                ALTER TABLE analyses 
                ADD COLUMN alert_id INTEGER REFERENCES alerts(id) ON DELETE CASCADE
            """)
            conn.commit()
            print("✓ Successfully added 'alert_id' column to analyses table")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    update_schema()
