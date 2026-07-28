"""
AI Infra Monitor - Unified Database Connection Module
Supports PostgreSQL local connections and Cloud PostgreSQL (Supabase, Neon, AWS RDS) with SSL.
"""

import os
import psycopg2
import logging

logger = logging.getLogger(__name__)


def get_db_connection():
    """
    Create and return a PostgreSQL database connection.
    Supports DATABASE_URL or individual DB_* environment variables with SSL auto-detection.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)
        
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "ai_infra_monitor")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    
    # Auto-enable sslmode for remote/cloud hosts (e.g., Supabase, Neon)
    sslmode = os.getenv("DB_SSLMODE")
    if not sslmode:
        if host not in ["localhost", "127.0.0.1", "0.0.0.0"]:
            sslmode = "require"
        else:
            sslmode = "prefer"
            
    conn_kwargs = {
        "dbname": dbname,
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "sslmode": sslmode,
        "connect_timeout": 15
    }
    
    return psycopg2.connect(**conn_kwargs)
