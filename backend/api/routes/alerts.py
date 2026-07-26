"""
AI Infra Monitor - Alerts API Routes

This module defines API endpoints for alerts management with multi-tenant org_id filtering.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Query, Header
from typing import List, Dict, Any, Optional
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


@router.get("/alerts")
async def get_alerts(
    status: Optional[str] = Query(None, description="Filter by status (open, closed)"),
    authorization: Optional[str] = Header(None)
) -> List[Dict[str, Any]]:
    """
    Get alerts filtered by current organization.
    """
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        if status:
            cursor.execute(
                """
                SELECT 
                    id,
                    host_id,
                    metric_name,
                    severity,
                    message,
                    status,
                    created_at
                FROM alerts
                WHERE org_id = %s AND status = %s
                ORDER BY created_at DESC
                """,
                (org_id, status)
            )
        else:
            cursor.execute(
                """
                SELECT 
                    id,
                    host_id,
                    metric_name,
                    severity,
                    message,
                    status,
                    created_at
                FROM alerts
                WHERE org_id = %s
                ORDER BY created_at DESC
                """,
                (org_id,)
            )
        
        alerts = cursor.fetchall()
        return [dict(alert) for alert in alerts]
        
    finally:
        cursor.close()
        conn.close()
