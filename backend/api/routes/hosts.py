"""
AI Infra Monitor - Hosts API Routes

This module defines API endpoints for host management with multi-tenant org_id filtering.
"""

import os
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Header
from backend.api.routes.auth import decode_jwt_token

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


def get_current_org_id(authorization: Optional[str] = None) -> int:
    """Extract org_id from JWT token in Authorization header."""
    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.split(" ")[1]
            payload = decode_jwt_token(token)
            return payload.get("org_id", 1)
        except Exception:
            pass
    return 1


import socket

@router.get("/hosts")
async def get_hosts(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Get all registered hosts filtered by current organization.
    Auto-provisions local computer if none exists for this organization.
    """
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute(
            """
            SELECT id, hostname, created_at
            FROM hosts
            WHERE org_id = %s
            ORDER BY id ASC
            """,
            (org_id,)
        )
        hosts = cursor.fetchall()
        
        if not hosts:
            local_hostname = socket.gethostname() or "local-host"
            cursor.execute(
                """
                INSERT INTO hosts (hostname, org_id)
                VALUES (%s, %s)
                ON CONFLICT (hostname) DO UPDATE SET org_id = EXCLUDED.org_id
                RETURNING id, hostname, created_at;
                """,
                (local_hostname, org_id)
            )
            new_host = cursor.fetchone()
            conn.commit()
            hosts = [new_host]

        return {"hosts": [dict(host) for host in hosts]}
        
    finally:
        cursor.close()
        conn.close()
