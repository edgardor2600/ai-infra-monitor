"""
AI Infra Monitor — Alerts API v2

Enriched endpoints exposing the full intelligent alert lifecycle:
  GET  /alerts              — Paginated alert list with AI diagnosis, occurrences, duration
  GET  /alerts/summary      — Real-time health summary for dashboard header
  GET  /alerts/{id}         — Full alert detail
  POST /alerts/{id}/acknowledge — Mark as acknowledged by current user
  POST /alerts/{id}/resolve     — Manual resolution
  GET  /incidents           — Correlated incident groups with AI root cause
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.api.routes.auth import decode_jwt_token

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

from backend.db.connection import get_db_connection


def get_current_user(authorization: Optional[str] = None) -> Dict[str, Any]:
    """Extract org_id and email from JWT. Defaults to org_id=1 for local dev."""
    if authorization and authorization.startswith("Bearer "):
        try:
            payload = decode_jwt_token(authorization.split(" ")[1])
            return {
                "org_id": payload.get("org_id", 1),
                "email":  payload.get("email", "unknown"),
            }
        except Exception:
            pass
    return {"org_id": 1, "email": "system"}


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class AcknowledgeRequest(BaseModel):
    note: Optional[str] = None


class ResolveRequest(BaseModel):
    resolution_note: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Serialization helper
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_alert(row: dict) -> dict:
    """Convert a DB alert row to a JSON-safe dict with formatted fields."""
    d = dict(row)
    for ts_field in ("created_at", "last_seen_at", "resolved_at", "acknowledged_at"):
        if d.get(ts_field):
            d[ts_field] = d[ts_field].isoformat()
    d.setdefault("occurrences_count", 1)
    d.setdefault("rule_name", "legacy")
    d.setdefault("ai_diagnosis", None)
    d.setdefault("ai_recommendation", None)
    d.setdefault("duration_seconds", None)
    return d


# ─────────────────────────────────────────────────────────────────────────────
# GET /alerts — Paginated list with enriched data
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/alerts")
async def get_alerts(
    status: Optional[str] = Query(None, description="Filter: open | resolved | acknowledged"),
    severity: Optional[str] = Query(None, description="Filter: CRITICAL | HIGH | MEDIUM | LOW"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Return enriched alerts for the current organization.
    Includes AI diagnosis, occurrence count, duration, and recommendation.
    """
    user = get_current_user(authorization)
    org_id = user["org_id"]

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        conditions = ["(a.org_id = %s OR (a.org_id IS NULL AND a.host_id IN (SELECT id FROM hosts WHERE org_id = %s)))"]
        params: list = [org_id, org_id]

        if status:
            conditions.append("status = %s")
            params.append(status)
        if severity:
            conditions.append("severity = %s")
            params.append(severity.upper())

        where_clause = " AND ".join(conditions)

        # Total count for pagination
        cursor.execute(f"SELECT COUNT(*) FROM alerts a WHERE {where_clause}", params)
        total = cursor.fetchone()["count"]

        params.extend([limit, offset])
        cursor.execute(
            f"""
            SELECT
                a.id,
                a.host_id,
                h.hostname,
                a.metric_name,
                a.severity,
                a.message,
                a.status,
                a.rule_name,
                a.threshold_value,
                a.actual_value,
                a.occurrences_count,
                a.last_seen_at,
                a.resolved_at,
                a.duration_seconds,
                a.ai_diagnosis,
                a.ai_recommendation,
                a.acknowledged_by,
                a.acknowledged_at,
                a.created_at
            FROM alerts a
            LEFT JOIN hosts h ON a.host_id = h.id
            WHERE {where_clause}
            ORDER BY
                CASE severity
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH'     THEN 2
                    WHEN 'MEDIUM'   THEN 3
                    WHEN 'LOW'      THEN 4
                    ELSE 5
                END,
                a.last_seen_at DESC NULLS LAST,
                a.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params,
        )
        rows = cursor.fetchall()
        alerts = [_serialize_alert(r) for r in rows]

        return {
            "ok": True,
            "alerts": alerts,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# GET /alerts/summary — Real-time health dashboard metrics
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/alerts/summary")
async def get_alerts_summary(
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Return real-time health metrics for the alert center header.
    Provides severity breakdown, resolution rate and avg resolution time.
    """
    user = get_current_user(authorization)
    org_id = user["org_id"]

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Open alerts by severity
        cursor.execute(
            """
            SELECT severity, COUNT(*) as count
            FROM alerts
            WHERE status = 'open'
              AND (org_id = %s OR (org_id IS NULL AND host_id IN
                  (SELECT id FROM hosts WHERE org_id = %s)))
            GROUP BY severity
            """,
            (org_id, org_id),
        )
        sev_rows = cursor.fetchall()
        by_severity = {r["severity"]: r["count"] for r in sev_rows}

        # Resolved today
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM alerts
            WHERE status = 'resolved'
              AND resolved_at >= NOW() - INTERVAL '24 hours'
              AND (org_id = %s OR (org_id IS NULL AND host_id IN
                  (SELECT id FROM hosts WHERE org_id = %s)))
            """,
            (org_id, org_id),
        )
        resolved_today = cursor.fetchone()["count"]

        # Average resolution time (seconds) for last 30 days
        cursor.execute(
            """
            SELECT AVG(duration_seconds) as avg_secs
            FROM alerts
            WHERE status = 'resolved'
              AND duration_seconds IS NOT NULL
              AND resolved_at >= NOW() - INTERVAL '30 days'
              AND (org_id = %s OR (org_id IS NULL AND host_id IN
                  (SELECT id FROM hosts WHERE org_id = %s)))
            """,
            (org_id, org_id),
        )
        avg_row = cursor.fetchone()
        avg_resolution_secs = avg_row["avg_secs"] if avg_row and avg_row["avg_secs"] else None

        # Total open
        total_open = sum(by_severity.values())

        # System health score (0-100)
        critical_weight = by_severity.get("CRITICAL", 0) * 25
        high_weight = by_severity.get("HIGH", 0) * 10
        medium_weight = by_severity.get("MEDIUM", 0) * 3
        penalty = min(100, critical_weight + high_weight + medium_weight)
        health_score = max(0, 100 - penalty)

        return {
            "ok": True,
            "total_open": total_open,
            "by_severity": {
                "CRITICAL": by_severity.get("CRITICAL", 0),
                "HIGH":     by_severity.get("HIGH", 0),
                "MEDIUM":   by_severity.get("MEDIUM", 0),
                "LOW":      by_severity.get("LOW", 0),
                "INFO":     by_severity.get("INFO", 0),
            },
            "resolved_today": resolved_today,
            "avg_resolution_seconds": int(avg_resolution_secs) if avg_resolution_secs else None,
            "health_score": health_score,
        }
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# GET /alerts/{id} — Full alert detail
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/alerts/{alert_id}")
async def get_alert_detail(
    alert_id: int,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Return complete details for a single alert including full AI diagnosis."""
    user = get_current_user(authorization)
    org_id = user["org_id"]

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT a.*, h.hostname
            FROM alerts a
            LEFT JOIN hosts h ON a.host_id = h.id
            WHERE a.id = %s
              AND (a.org_id = %s OR (a.org_id IS NULL AND a.host_id IN
                  (SELECT id FROM hosts WHERE org_id = %s)))
            """,
            (alert_id, org_id, org_id),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"ok": True, "alert": _serialize_alert(row)}
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# POST /alerts/{id}/acknowledge
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    body: AcknowledgeRequest = AcknowledgeRequest(),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Mark alert as acknowledged by the current user."""
    user = get_current_user(authorization)
    org_id = user["org_id"]
    email = user["email"]

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE alerts
            SET
                status           = 'acknowledged',
                acknowledged_by  = %s,
                acknowledged_at  = NOW()
            WHERE id = %s
              AND (org_id = %s OR (org_id IS NULL AND host_id IN
                  (SELECT id FROM hosts WHERE org_id = %s)))
              AND status = 'open'
            RETURNING id
            """,
            (email, alert_id, org_id, org_id),
        )
        updated = cursor.fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Alert not found or already resolved")
        conn.commit()
        return {"ok": True, "message": f"Alert {alert_id} acknowledged by {email}"}
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# POST /alerts/{id}/resolve
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    body: ResolveRequest = ResolveRequest(),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Manually resolve an alert with an optional resolution note."""
    user = get_current_user(authorization)
    org_id = user["org_id"]
    email = user["email"]

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        note_suffix = f" — Note: {body.resolution_note}" if body.resolution_note else ""

        cursor.execute(
            """
            UPDATE alerts
            SET
                status           = 'resolved',
                resolved_at      = NOW(),
                acknowledged_by  = %s,
                ai_recommendation = COALESCE(ai_recommendation, '') || %s,
                duration_seconds = EXTRACT(EPOCH FROM (NOW() - created_at))::INTEGER
            WHERE id = %s
              AND (org_id = %s OR (org_id IS NULL AND host_id IN
                  (SELECT id FROM hosts WHERE org_id = %s)))
              AND status != 'resolved'
            RETURNING id
            """,
            (email, note_suffix, alert_id, org_id, org_id),
        )
        updated = cursor.fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Alert not found or already resolved")
        conn.commit()
        return {"ok": True, "message": f"Alert {alert_id} resolved manually by {email}"}
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# GET /incidents — Correlated incident groups
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/incidents")
async def get_incidents(
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Return correlated incident groups for the current organization."""
    user = get_current_user(authorization)
    org_id = user["org_id"]

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Check if incidents table exists
        cursor.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'incidents')"
        )
        if not cursor.fetchone()["exists"]:
            return {"ok": True, "incidents": [], "total": 0}

        params = [org_id]
        where = "i.org_id = %s"
        if status:
            where += " AND i.status = %s"
            params.append(status)
        params.append(limit)

        cursor.execute(
            f"""
            SELECT i.*, h.hostname
            FROM incidents i
            LEFT JOIN hosts h ON i.host_id = h.id
            WHERE {where}
            ORDER BY i.created_at DESC
            LIMIT %s
            """,
            params,
        )
        rows = cursor.fetchall()

        incidents = []
        for r in rows:
            d = dict(r)
            for f in ("created_at", "updated_at", "acknowledged_at", "resolved_at"):
                if d.get(f):
                    d[f] = d[f].isoformat()
            incidents.append(d)

        return {"ok": True, "incidents": incidents, "total": len(incidents)}
    finally:
        cursor.close()
        conn.close()
