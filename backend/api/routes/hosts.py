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

from backend.db.connection import get_db_connection


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


@router.post("/hosts/register")
async def register_host(payload: Dict[str, Any]):
    """Auto-register host by hostname when agent connects."""
    hostname = payload.get("hostname")
    if not hostname:
        raise HTTPException(status_code=400, detail="Hostname required")
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO hosts (hostname, org_id)
            VALUES (%s, 1)
            ON CONFLICT (hostname) DO UPDATE SET hostname = EXCLUDED.hostname
            RETURNING id, hostname;
            """,
            (hostname,)
        )
        row = cursor.fetchone()
        conn.commit()
        return {"id": row['id'], "hostname": row['hostname']}
    finally:
        cursor.close()
        conn.close()
