"""
Tests for worker process_host_v2 function and AlertEngine integration.
"""

from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from backend.worker.worker import process_host
from backend.worker.alert_engine import AlertEngine, AlertUpsertResult
from backend.worker.rules import RuleResult


@pytest.mark.asyncio
async def test_alert_engine_upsert():
    """Test that AlertEngine upserts an alert into the database."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    # No existing open alert, new alert id 123
    mock_cursor.fetchone.side_effect = [None, [123]]
    mock_conn.cursor.return_value = mock_cursor

    rule_res = RuleResult(
        rule_name="cpu_sustained",
        metric="cpu_percent",
        severity="HIGH",
        message="CPU usage sustained at 93%",
        threshold_value=85.0,
        actual_value=93.0,
        recommendation="Investigate heavy processes"
    )

    upsert_res = await AlertEngine.evaluate_and_upsert(
        mock_conn,
        host_id=1,
        org_id=1,
        rule_result=rule_res
    )

    assert upsert_res.alert_id == 123
    assert upsert_res.was_new is True
    assert mock_cursor.execute.call_count >= 1


@pytest.mark.asyncio
async def test_process_host_v2_creates_alerts():
    """Test process_host evaluating rules and upserting alerts."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Metric values returned by snapshot collector
    mock_cursor.fetchone.side_effect = [
        (96.0,),  # cpu 30s
        (96.0,),  # cpu 180s
        (30.0,),  # cpu baseline
        (85.0,),  # mem pct
        (500.0,), # mem free mb
        (85.0,),  # mem 5min
        (95.0,),  # disk pct
        (10.0,),  # disk free gb
        (50.0,),  # disk free 24h
        (datetime.now(timezone.utc) - timedelta(minutes=1),), # last_seen timestamp
    ]

    mock_conn.cursor.return_value = mock_cursor

    mock_upsert_res = AlertUpsertResult(
        alert_id=456,
        was_new=True,
        was_escalated=False,
        rule_name="cpu_sustained",
        severity="CRITICAL"
    )

    with patch.object(AlertEngine, 'evaluate_and_upsert', new_callable=AsyncMock) as mock_upsert:
        mock_upsert.return_value = mock_upsert_res

        results = await process_host(host_id=1, conn=mock_conn, org_id=1)

        assert isinstance(results, list)
        assert len(results) >= 1
        assert any(res.rule_name == "cpu_sustained" for res in results)
