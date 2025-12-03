"""
AI Infra Monitor - Dashboard API Routes

This module provides endpoints for dashboard overview statistics.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter
from typing import Dict, Any, List

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

@router.get("/dashboard/overview")
async def get_dashboard_overview() -> Dict[str, Any]:
    """
    Get dashboard overview statistics.
    
    Returns:
        Dictionary containing:
        - total_hosts: Total number of monitored hosts
        - active_alerts: Count of alerts by severity
        - recent_alerts: Last 5 alerts
        - hosts_status: Health status of each host
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get total hosts
        cursor.execute("SELECT COUNT(*) as count FROM hosts")
        total_hosts = cursor.fetchone()['count']
        
        # Get active alerts by severity
        cursor.execute("""
            SELECT 
                severity,
                COUNT(*) as count
            FROM alerts
            WHERE status = 'open'
            GROUP BY severity
        """)
        alerts_by_severity = {row['severity']: row['count'] for row in cursor.fetchall()}
        
        # Get total active alerts
        total_active_alerts = sum(alerts_by_severity.values())
        
        # Get recent alerts (last 5)
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
            WHERE a.status = 'open'
            ORDER BY a.created_at DESC
            LIMIT 5
        """)
        recent_alerts = [dict(row) for row in cursor.fetchall()]
        
        # Get hosts with their latest metrics and alert counts
        cursor.execute("""
            WITH latest_metrics AS (
                SELECT DISTINCT ON (host_id)
                    host_id,
                    payload,
                    created_at
                FROM metrics_raw
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
            
            # Extract metrics from payload
            cpu_percent = 0
            mem_percent = 0
            
            if host.get('payload') and 'samples' in host['payload']:
                for sample in host['payload']['samples']:
                    if sample.get('metric') == 'cpu_percent':
                        cpu_percent = sample.get('value', 0)
                    elif sample.get('metric') == 'mem_percent':
                        mem_percent = sample.get('value', 0)
            
            # Remove payload from result to keep it clean
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
