"""
AI Infra Monitor — Worker Module v2

Processes incoming host metrics, evaluates all intelligent rules,
delegates alert lifecycle to AlertEngine and logs notifications.

Key changes vs. v1:
  - Reads CPU + Memory + Disk + Heartbeat metrics from DB
  - Uses multi-window aggregation (30s / 3min / 5min / 1h baseline)
  - Delegates deduplication, escalation and auto-resolution to AlertEngine
  - No more alert storms: each condition produces at most 1 active open alert
"""

import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor

from backend.worker.rules import evaluate_all_rules, RuleResult
from backend.worker.alert_engine import AlertEngine, AlertUpsertResult

logger = logging.getLogger(__name__)


def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "123"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Metric collection helpers
# ─────────────────────────────────────────────────────────────────────────────

def _avg_metric(cursor, host_id: int, metric: str, interval_seconds: int) -> float:
    """
    Compute the average of a specific metric for a host over the given window.
    Reads from the metrics_raw JSONB payload structure.
    """
    cursor.execute(
        """
        SELECT AVG((sample->>'value')::float)
        FROM metrics_raw,
             jsonb_array_elements(payload->'samples') AS sample
        WHERE host_id = %s
          AND sample->>'metric' = %s
          AND created_at >= NOW() - INTERVAL %s
        """,
        (host_id, metric, f"{interval_seconds} seconds"),
    )
    row = cursor.fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def _latest_metric(cursor, host_id: int, metric: str) -> float:
    """Get the single most recent value for a metric, within the last 24 hours.
    Returns 0.0 if no recent data exists (prevents stale/synthetic values from old rows).
    """
    cursor.execute(
        """
        SELECT (sample->>'value')::float
        FROM metrics_raw,
             jsonb_array_elements(payload->'samples') AS sample
        WHERE host_id = %s
          AND sample->>'metric' = %s
          AND created_at >= NOW() - INTERVAL '24 hours'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (host_id, metric),
    )
    row = cursor.fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def _minutes_since_last_report(cursor, host_id: int) -> float:
    """Return how many minutes have passed since the last metric batch was received."""
    cursor.execute(
        "SELECT MAX(created_at) FROM metrics_raw WHERE host_id = %s",
        (host_id,),
    )
    row = cursor.fetchone()
    if not row or row[0] is None:
        return 999.0  # Never reported
    last_seen = row[0]
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - last_seen
    return delta.total_seconds() / 60.0


def _collect_metrics_snapshot(cursor, host_id: int) -> Dict[str, Any]:
    """
    Build a full metrics snapshot for rule evaluation.
    Aggregates multiple time windows and metric types in a single pass.
    """
    return {
        # CPU windows
        "avg_cpu_30s":      _avg_metric(cursor, host_id, "cpu_percent", 30),
        "avg_cpu_180s":     _avg_metric(cursor, host_id, "cpu_percent", 180),
        "avg_cpu_baseline": _avg_metric(cursor, host_id, "cpu_percent", 3600),  # 1h baseline

        # Memory
        "mem_used_pct":  _latest_metric(cursor, host_id, "mem_percent"),
        "mem_free_mb":   _latest_metric(cursor, host_id, "mem_free_mb"),
        "avg_mem_5min":  _avg_metric(cursor, host_id, "mem_percent", 300),

        # Disk
        "disk_used_pct":    _latest_metric(cursor, host_id, "disk_percent"),
        "disk_free_gb":     _latest_metric(cursor, host_id, "disk_free_gb"),
        "disk_free_gb_24h": _avg_metric(cursor, host_id, "disk_free_gb", 86400),  # 24h ago snapshot
        "drive":            "C:",

        # Heartbeat
        "minutes_silent": _minutes_since_last_report(cursor, host_id),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Notification log
# ─────────────────────────────────────────────────────────────────────────────

async def _log_alert_notification(result: AlertUpsertResult, host_id: int) -> None:
    """Log alert events for notification pipeline (email/webhook hooks can attach here)."""
    try:
        from backend.worker.notifications import log_alert
        log_alert({
            "id":         result.alert_id,
            "host_id":    host_id,
            "rule_name":  result.rule_name,
            "severity":   result.severity,
            "was_new":    result.was_new,
            "escalated":  result.was_escalated,
            "status":     "open",
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.debug(f"Notification log skipped: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Main processing entry point
# ─────────────────────────────────────────────────────────────────────────────

async def process_host(host_id: int, conn, org_id: int = 1) -> List[AlertUpsertResult]:
    """
    Full alert cycle for one host:
      1. Collect multi-window metrics from DB
      2. Auto-resolve any open alerts whose conditions normalized
      3. Evaluate all 7 intelligent rules
      4. Upsert alerts (create new OR update existing via AlertEngine)
      5. Return list of AlertUpsertResult for logging/monitoring

    Args:
        host_id: ID of the host to evaluate
        conn:    Active psycopg2 database connection
        org_id:  Organization ID for multi-tenant isolation

    Returns:
        List of AlertUpsertResult objects (one per triggered rule)
    """
    cursor = conn.cursor()

    # ── Step 1: Collect metrics snapshot ─────────────────────────────────────
    try:
        snapshot = _collect_metrics_snapshot(cursor, host_id)
        cursor.close()
    except Exception as e:
        cursor.close()
        logger.error(f"Failed to collect metrics for host {host_id}: {e}")
        return []

    logger.info(
        f"Host {host_id} | "
        f"CPU 30s={snapshot['avg_cpu_30s']:.1f}% 3min={snapshot['avg_cpu_180s']:.1f}% | "
        f"MEM={snapshot['mem_used_pct']:.1f}% | "
        f"DISK free={snapshot['disk_free_gb']:.1f}GB | "
        f"silent={snapshot['minutes_silent']:.1f}min"
    )

    # ── Step 2: Auto-resolve normalized conditions ────────────────────────────
    try:
        resolved = await AlertEngine.auto_resolve_normalized_alerts(
            conn, host_id, org_id, snapshot
        )
        if resolved:
            logger.info(f"Host {host_id}: Auto-resolved {len(resolved)} alert(s): {resolved}")
    except Exception as e:
        logger.warning(f"Auto-resolve pass failed for host {host_id}: {e}")

    # ── Step 3: Evaluate rules ────────────────────────────────────────────────
    triggered_rules: List[RuleResult] = evaluate_all_rules(snapshot)

    if not triggered_rules:
        logger.info(f"Host {host_id}: All metrics normal — no alerts triggered ✅")
        return []

    logger.info(
        f"Host {host_id}: {len(triggered_rules)} rule(s) triggered: "
        f"{[r.rule_name for r in triggered_rules]}"
    )

    # ── Step 4: Upsert alerts via AlertEngine ─────────────────────────────────
    results: List[AlertUpsertResult] = []

    for rule_result in triggered_rules:
        try:
            upsert_result = await AlertEngine.evaluate_and_upsert(
                conn, host_id, org_id, rule_result
            )
            results.append(upsert_result)

            # Only send notifications for new or escalated alerts
            if upsert_result.was_new or upsert_result.was_escalated:
                await _log_alert_notification(upsert_result, host_id)

        except Exception as e:
            logger.error(
                f"AlertEngine upsert failed for host={host_id} "
                f"rule={rule_result.rule_name}: {e}"
            )

    new_count = sum(1 for r in results if r.was_new)
    updated_count = sum(1 for r in results if not r.was_new and not r.was_escalated)
    escalated_count = sum(1 for r in results if r.was_escalated)

    logger.info(
        f"Host {host_id} cycle complete: "
        f"{new_count} new | {updated_count} updated | {escalated_count} escalated"
    )

    return results
