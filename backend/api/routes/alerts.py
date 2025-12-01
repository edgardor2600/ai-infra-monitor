"""
AI Infra Monitor - Alerts API Routes

This module defines API endpoints for alerts management.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional

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

@router.get("/alerts")
async def get_alerts(
    status: Optional[str] = Query(None, description="Filter by status (open, closed)")
) -> List[Dict[str, Any]]:
    """
    Get alerts, optionally filtered by status.
    
    Args:
        status: Optional status filter ('open' or 'closed')
        
    Returns:
        List of alerts with all details
    """
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
                WHERE status = %s
                ORDER BY created_at DESC
                """,
                (status,)
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
                ORDER BY created_at DESC
                """
            )
        
        alerts = cursor.fetchall()
        return [dict(alert) for alert in alerts]
        
    finally:
        cursor.close()
        conn.close()

@router.get("/alerts/{alert_id}/analysis")
async def get_alert_analysis(alert_id: int) -> Dict[str, Any]:
    """
    Get the analysis result for a specific alert.
    
    Args:
        alert_id: ID of the alert
        
    Returns:
        Analysis result if exists
        
    Raises:
        HTTPException: 404 if no analysis found
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute(
            """
            SELECT 
                id,
                alert_id,
                result,
                created_at
            FROM analyses
            WHERE alert_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (alert_id,)
        )
        
        analysis = cursor.fetchone()
        
        if not analysis:
            raise HTTPException(status_code=404, detail="No analysis found for this alert")
        
        return dict(analysis)
        
    finally:
        cursor.close()
        conn.close()
