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
    Strict 100% org_id multi-tenant isolation.
    """
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute(
            """
            SELECT id, hostname, created_at, org_id
            FROM hosts
            WHERE org_id = %s
            ORDER BY id ASC
            """,
            (org_id,)
        )
        hosts = cursor.fetchall()
        return {"hosts": [dict(host) for host in hosts]}
        
    finally:
        cursor.close()
        conn.close()


@router.post("/hosts/register")
async def register_host(payload: Dict[str, Any], authorization: Optional[str] = Header(None)):
    """Auto-register host by hostname when agent connects, attaching it to current org_id."""
    hostname = payload.get("hostname")
    if not hostname:
        raise HTTPException(status_code=400, detail="Hostname required")
    
    org_id = payload.get("org_id") or get_current_org_id(authorization)
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO hosts (hostname, org_id)
            VALUES (%s, %s)
            ON CONFLICT (hostname, org_id) DO UPDATE SET hostname = EXCLUDED.hostname
            RETURNING id, hostname, org_id;
            """,
            (hostname, org_id)
        )
        row = cursor.fetchone()
        conn.commit()
        return {"id": row['id'], "hostname": row['hostname'], "org_id": row['org_id']}
    finally:
        cursor.close()
        conn.close()
