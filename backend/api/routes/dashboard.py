"""
AI Infra Monitor - Dashboard API Routes

This module provides endpoints for dashboard overview statistics with multi-tenant org_id filtering.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Header
from typing import Dict, Any, List, Optional
from backend.api.routes.auth import decode_jwt_token, get_current_org_id

router = APIRouter()

from backend.db.connection import get_db_connection


@router.get("/dashboard/overview")
async def get_dashboard_overview(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Get dashboard overview statistics filtered by current organization.
    """
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get total hosts for organization
        cursor.execute("SELECT COUNT(*) as count FROM hosts WHERE org_id = %s", (org_id,))
        total_hosts = cursor.fetchone()['count']
        
        # Get active alerts by severity for organization
        cursor.execute("""
            SELECT 
                severity,
                COUNT(*) as count
            FROM alerts
            WHERE org_id = %s AND status = 'open'
            GROUP BY severity
        """, (org_id,))
        alerts_by_severity = {row['severity']: row['count'] for row in cursor.fetchall()}
        
        # Get total active alerts
        total_active_alerts = sum(alerts_by_severity.values())
        
        # Get recent alerts (last 5) for organization
        cursor.execute("""
            SELECT 
                a.id,
                a.host_id,
                h.hostname,
                a.metric_name,
                a.severity,
                a.message,
                a.created_at
            FROM alerts a
            JOIN hosts h ON a.host_id = h.id
            WHERE a.org_id = %s AND a.status = 'open'
            ORDER BY a.created_at DESC
            LIMIT 5
        """, (org_id,))
        recent_alerts = [dict(row) for row in cursor.fetchall()]
        
        # Get hosts with their latest metrics and alert counts for organization
        cursor.execute("""
            WITH latest_metrics AS (
                SELECT DISTINCT ON (host_id)
                    host_id,
                    payload,
                    created_at
                FROM metrics_raw
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                ORDER BY host_id, created_at DESC
            ),
            host_alerts AS (
                SELECT 
                    host_id,
                    COUNT(*) as alert_count
                FROM alerts
                WHERE org_id = %s AND status = 'open'
                GROUP BY host_id
            )
            SELECT 
                h.id,
                h.hostname,
                h.created_at as registered_at,
                lm.payload,
                COALESCE(lm.created_at, h.created_at) as last_seen,
            FROM hosts h
            LEFT JOIN latest_metrics lm ON h.id = lm.host_id
            LEFT JOIN host_alerts ha ON h.id = ha.host_id
            WHERE h.org_id = %s
            ORDER BY h.hostname
        """, (org_id, org_id))
        hosts_data = cursor.fetchall()

        # Fallback for new accounts: if new org has no hosts yet, show default hosts
        if not hosts_data and org_id != 1:
            cursor.execute("""
                WITH latest_metrics AS (
                    SELECT DISTINCT ON (host_id)
                        host_id,
                        payload,
                        created_at
                    FROM metrics_raw
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY host_id, created_at DESC
                ),
                host_alerts AS (
                    SELECT 
                        host_id,
                        COUNT(*) as alert_count
                    FROM alerts
                    WHERE status = 'open'
                    GROUP BY host_id
                )
                SELECT 
                    h.id,
                    h.hostname,
                    h.created_at as registered_at,
                    lm.payload,
                    COALESCE(lm.created_at, h.created_at) as last_seen,
                    COALESCE(ha.alert_count, 0) as alert_count
                FROM hosts h
                LEFT JOIN latest_metrics lm ON h.id = lm.host_id
                LEFT JOIN host_alerts ha ON h.id = ha.host_id
                ORDER BY h.hostname
            """)
            hosts_data = cursor.fetchall()
        hosts_status = []
        
        for row in hosts_data:
            host = dict(row)
            
            cpu_percent = 0
            mem_percent = 0
            
            if host.get('payload') and 'samples' in host['payload']:
                for sample in host['payload']['samples']:
                    if sample.get('metric') == 'cpu_percent':
                        cpu_percent = sample.get('value', 0)
                    elif sample.get('metric') == 'mem_percent':
                        mem_percent = sample.get('value', 0)
            
            del host['payload']
            
            host['cpu_percent'] = cpu_percent
            host['mem_percent'] = mem_percent
            
            hosts_status.append(host)
        
        return {
            "total_hosts": total_hosts,
            "total_active_alerts": total_active_alerts,
            "alerts_by_severity": {
                "HIGH": alerts_by_severity.get("HIGH", 0),
                "MEDIUM": alerts_by_severity.get("MEDIUM", 0),
                "LOW": alerts_by_severity.get("LOW", 0)
            },
            "recent_alerts": recent_alerts,
            "hosts_status": hosts_status
        }
        
    finally:
        cursor.close()
        conn.close()
