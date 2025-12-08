"""
Register current host in the database.
"""

import os
import socket
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Create a database connection."""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

def register_host():
    """Register the current host if not already registered."""
    hostname = socket.gethostname()
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Check if host already exists
        cursor.execute(
            "SELECT id, hostname FROM hosts WHERE hostname = %s",
            (hostname,)
        )
        existing_host = cursor.fetchone()
        
        if existing_host:
            print(f"Host '{hostname}' already registered with ID: {existing_host['id']}")
            return existing_host['id']
        
        # Register new host
        cursor.execute(
            "INSERT INTO hosts (hostname) VALUES (%s) RETURNING id",
            (hostname,)
        )
        host_id = cursor.fetchone()['id']
        conn.commit()
        
        print(f"Successfully registered host '{hostname}' with ID: {host_id}")
        print(f"\nTo use this host with the agent, set:")
        print(f"  AGENT_HOST_ID={host_id}")
        
        return host_id
        
    except Exception as e:
        print(f"Error registering host: {e}")
        conn.rollback()
        raise
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    register_host()
