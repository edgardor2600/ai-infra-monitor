"""
AI Infra Monitor - Hosts API Routes

This module defines API endpoints for host management.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

router = APIRouter()

def get_db_connection():
    """Create a database connection."""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

@router.get("/hosts")
async def get_hosts() -> Dict[str, Any]:
    """
    Get all registered hosts.
    
    Returns:
        Dictionary with 'hosts' key containing list of hosts with id, hostname, and created_at
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute(
            """
            SELECT id, hostname, created_at
            FROM hosts
            ORDER BY id ASC
            """
        )
        hosts = cursor.fetchall()
        return {"hosts": [dict(host) for host in hosts]}
        
    finally:
        cursor.close()
        conn.close()
