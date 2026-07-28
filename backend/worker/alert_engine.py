"""
AI Infra Monitor — Alert Engine v2

Core intelligence layer between rule evaluation and database persistence.

Responsibilities:
  1. Deduplication — prevent alert storms by updating existing open alerts
  2. Severity escalation — upgrade severity if a condition worsens over time
  3. Auto-resolution — mark alerts resolved when metrics normalize
  4. AI diagnosis — trigger async LLM analysis for every new real alert
  5. Incident grouping — correlate simultaneous alerts into a single incident
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from backend.worker.rules import RuleResult

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

SEVERITY_ORDER = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
COOLDOWN_MINUTES = 5  # Default cooldown between creating new alert records


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

class AlertUpsertResult:
    """Result of an alert upsert operation."""

    def __init__(
        self,
        alert_id: int,
        was_new: bool,
        was_escalated: bool,
        rule_name: str,
        severity: str,
    ):
        self.alert_id = alert_id
        self.was_new = was_new
        self.was_escalated = was_escalated
        self.rule_name = rule_name
        self.severity = severity

    def __repr__(self):
        action = "NEW" if self.was_new else ("ESCALATED" if self.was_escalated else "UPDATED")
        return f"<AlertUpsertResult id={self.alert_id} action={action} rule={self.rule_name}>"


# ─────────────────────────────────────────────────────────────────────────────
# AlertEngine
# ─────────────────────────────────────────────────────────────────────────────

class AlertEngine:
    """
    Stateless engine — all state lives in PostgreSQL.
    Pass a live psycopg2 connection to each method call.
    """

    # ── Upsert ────────────────────────────────────────────────────────────────

    @staticmethod
    async def evaluate_and_upsert(
        conn,
        host_id: int,
        org_id: int,
        rule_result: RuleResult,
    ) -> AlertUpsertResult:
        """
        Either create a new alert or update an existing open one for the same rule+host.

        Logic:
        - Find any 'open' alert for this host + rule_name created within cooldown window.
        - If found:  increment occurrences_count, update last_seen_at, maybe escalate severity.
        - If not found: INSERT new alert with full enriched data.
        """
        cursor = conn.cursor()
        cooldown_interval = f"{rule_result.cooldown_minutes} minutes"

        # ── Check for existing open alert (within cooldown) ───────────────────
        cursor.execute(
            """
            SELECT id, severity, occurrences_count
            FROM alerts
            WHERE host_id = %s
              AND org_id = %s
              AND rule_name = %s
              AND status = 'open'
              AND last_seen_at >= NOW() - INTERVAL %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (host_id, org_id, rule_result.rule_name, cooldown_interval),
        )
        existing = cursor.fetchone()

        now = datetime.now(timezone.utc)

        if existing:
            existing_id, existing_severity, occ_count = existing
            new_count = (occ_count or 1) + 1

            # Determine if severity needs escalation
            current_rank = SEVERITY_ORDER.get(existing_severity, 0)
            new_rank = SEVERITY_ORDER.get(rule_result.severity, 0)
            was_escalated = new_rank > current_rank
            final_severity = rule_result.severity if was_escalated else existing_severity

            cursor.execute(
                """
                UPDATE alerts
                SET
                    occurrences_count = %s,
                    last_seen_at      = %s,
                    actual_value      = %s,
                    severity          = %s,
                    message           = %s
                WHERE id = %s
                """,
                (
                    new_count,
                    now,
                    rule_result.actual_value,
                    final_severity,
                    rule_result.message,
                    existing_id,
                ),
            )
            conn.commit()
            cursor.close()

            logger.debug(
                f"Alert UPDATED: id={existing_id} rule={rule_result.rule_name} "
                f"occ={new_count} escalated={was_escalated}"
            )
            return AlertUpsertResult(
                alert_id=existing_id,
                was_new=False,
                was_escalated=was_escalated,
                rule_name=rule_result.rule_name,
                severity=final_severity,
            )

        # ── No existing alert — create new one ────────────────────────────────
        cursor.execute(
            """
            INSERT INTO alerts (
                host_id, org_id, metric_name, severity, message, status,
                rule_name, threshold_value, actual_value,
                occurrences_count, last_seen_at, created_at
            )
            VALUES (%s, %s, %s, %s, %s, 'open', %s, %s, %s, 1, %s, %s)
            RETURNING id
            """,
            (
                host_id,
                org_id,
                rule_result.metric,
                rule_result.severity,
                rule_result.message,
                rule_result.rule_name,
                rule_result.threshold_value,
                rule_result.actual_value,
                now,
                now,
            ),
        )
        alert_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()

        logger.info(
            f"Alert CREATED: id={alert_id} rule={rule_result.rule_name} "
            f"severity={rule_result.severity} host={host_id}"
        )

        # Trigger AI diagnosis asynchronously (non-blocking)
        asyncio.create_task(
            AlertEngine.trigger_ai_diagnosis(conn, alert_id, rule_result, host_id)
        )

        return AlertUpsertResult(
            alert_id=alert_id,
            was_new=True,
            was_escalated=False,
            rule_name=rule_result.rule_name,
            severity=rule_result.severity,
        )

    # ── Auto-resolution ───────────────────────────────────────────────────────

    @staticmethod
    async def auto_resolve_normalized_alerts(
        conn,
        host_id: int,
        org_id: int,
        current_metrics: Dict[str, Any],
    ) -> List[int]:
        """
        Scan open alerts for this host and resolve any whose condition
        is no longer triggered by the current metrics snapshot.

        Returns list of alert IDs that were auto-resolved.
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, rule_name, created_at
            FROM alerts
            WHERE host_id = %s AND org_id = %s AND status = 'open'
            ORDER BY created_at ASC
            """,
            (host_id, org_id),
        )
        open_alerts = cursor.fetchall()
        cursor.close()

        resolved_ids = []
        now = datetime.now(timezone.utc)

        for alert_id, rule_name, created_at in open_alerts:
            if _is_condition_resolved(rule_name, current_metrics):
                duration = int((now - created_at.replace(tzinfo=timezone.utc)).total_seconds())
                cursor2 = conn.cursor()
                cursor2.execute(
                    """
                    UPDATE alerts
                    SET
                        status           = 'resolved',
                        resolved_at      = %s,
                        duration_seconds = %s
                    WHERE id = %s
                    """,
                    (now, duration, alert_id),
                )
                conn.commit()
                cursor2.close()
                resolved_ids.append(alert_id)
                logger.info(
                    f"Alert AUTO-RESOLVED: id={alert_id} rule={rule_name} "
                    f"duration={duration}s"
                )

        return resolved_ids

    # ── AI Diagnosis ──────────────────────────────────────────────────────────

    @staticmethod
    async def trigger_ai_diagnosis(
        conn,
        alert_id: int,
        rule_result: RuleResult,
        host_id: int,
    ) -> None:
        """
        Build a context-rich prompt and call the LLM to generate a diagnosis
        and actionable recommendation. Store result back in the alerts table.
        """
        try:
            from backend.app.llm_adapter import LLMAdapter

            prompt = _build_diagnosis_prompt(rule_result, host_id)
            adapter = LLMAdapter()

            raw_response = await adapter.analyze_disk_report(prompt)

            # Parse structured response or use raw text
            diagnosis, recommendation = _parse_ai_response(raw_response, rule_result)

            # Write back to DB using a fresh connection to avoid concurrency issues
            import os, psycopg2
            fresh_conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "123"),
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
            )
            cursor = fresh_conn.cursor()
            cursor.execute(
                """
                UPDATE alerts
                SET ai_diagnosis = %s, ai_recommendation = %s
                WHERE id = %s
                """,
                (diagnosis, recommendation, alert_id),
            )
            fresh_conn.commit()
            cursor.close()
            fresh_conn.close()

            logger.info(f"AI diagnosis stored for alert id={alert_id}")

        except Exception as e:
            logger.warning(f"AI diagnosis failed for alert {alert_id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_condition_resolved(rule_name: str, metrics: Dict[str, Any]) -> bool:
    """Return True if the metric that triggered the rule is now back to normal."""
    rule_resolution_map = {
        "cpu_sustained":        lambda m: m.get("avg_cpu_180s", 100) < 75,
        "cpu_anomaly_spike":    lambda m: m.get("avg_cpu_30s", 100) < 70,
        "memory_critical":      lambda m: m.get("mem_used_pct", 100) < 85,
        "memory_high_sustained": lambda m: m.get("avg_mem_5min", 100) < 80,
        "disk_critical":        lambda m: m.get("disk_free_gb", 0) > 8.0,
        "disk_trend_runaway":   lambda m: True,  # Always resolve trend alerts daily
        "host_silent":          lambda m: m.get("minutes_silent", 99) < 2,
    }
    resolver = rule_resolution_map.get(rule_name)
    return resolver(metrics) if resolver else False


def _build_diagnosis_prompt(rule_result: RuleResult, host_id: int) -> str:
    """Build an expert-level diagnostic prompt for the LLM."""
    return f"""You are an expert IT infrastructure analyst. A monitoring alert was triggered on host ID {host_id}.

ALERT DETAILS:
- Rule: {rule_result.rule_name}
- Metric: {rule_result.metric}
- Severity: {rule_result.severity}
- Measured value: {rule_result.actual_value:.1f}
- Alert threshold: {rule_result.threshold_value:.1f}
- Alert message: {rule_result.message}

Please provide:
1. DIAGNOSIS (2-3 sentences): What is likely causing this condition and what is its potential business impact?
2. RECOMMENDATION (2-4 actionable steps): Specific steps the operator should take right now.

Keep the response concise, technical and immediately actionable. Do not repeat the alert message.
Format: 
DIAGNOSIS: <text>
RECOMMENDATION: <numbered steps>"""


def _parse_ai_response(raw: str, rule_result: RuleResult) -> Tuple[str, str]:
    """
    Parse LLM response into (diagnosis, recommendation) tuple.
    Falls back to rule-level recommendation if parsing fails.
    """
    try:
        diagnosis = ""
        recommendation = ""

        if "DIAGNOSIS:" in raw and "RECOMMENDATION:" in raw:
            parts = raw.split("RECOMMENDATION:")
            diagnosis_part = parts[0].replace("DIAGNOSIS:", "").strip()
            recommendation_part = parts[1].strip() if len(parts) > 1 else ""
            diagnosis = diagnosis_part[:1000]
            recommendation = recommendation_part[:2000]
        else:
            # Fallback: use entire response as diagnosis
            diagnosis = raw[:1000]
            recommendation = rule_result.recommendation

        return diagnosis or rule_result.message, recommendation or rule_result.recommendation

    except Exception:
        return rule_result.message, rule_result.recommendation
