"""
Tests for worker notifications.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from backend.worker.notifications import log_alert
from backend.worker.alert_engine import AlertEngine
from backend.worker.rules import RuleResult


def test_log_alert_format(capsys):
    """Test that log_alert prints the correct JSON format."""
    alert = {
        "id": 123,
        "host_id": 1,
        "metric_name": "cpu_percent",
        "severity": "HIGH",
        "message": "CPU > 90%",
        "status": "open"
    }

    log_alert(alert)

    captured = capsys.readouterr()
    output = captured.out

    assert "ALERT CREATED" in output
    assert '"id": 123' in output
    assert '"severity": "HIGH"' in output

    json_str = output.replace("ALERT CREATED ", "").strip()
    parsed = json.loads(json_str)
    assert parsed["id"] == 123
    assert parsed["severity"] == "HIGH"


@pytest.mark.asyncio
async def test_alert_engine_calls_notification():
    """Test that AlertEngine logs notification when a new alert is created."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    # Return no existing open alert, then return new alert ID 999
    mock_cursor.fetchone.side_effect = [None, [999]]
    mock_conn.cursor.return_value = mock_cursor

    rule_res = RuleResult(
        rule_name="cpu_sustained",
        metric="cpu_percent",
        severity="HIGH",
        message="CPU sustained at 90%",
        threshold_value=85.0,
        actual_value=90.0,
        recommendation="Check top process"
    )

    with patch("backend.worker.notifications.log_alert") as mock_log:
        res = await AlertEngine.evaluate_and_upsert(
            mock_conn,
            host_id=1,
            org_id=1,
            rule_result=rule_res
        )

        assert res.alert_id == 999
        assert res.was_new is True


@pytest.mark.asyncio
async def test_notification_dispatcher_slack_payload():
    """Test formatting Slack webhook payloads."""
    from backend.app.notifications_dispatcher import NotificationDispatcher
    payload = NotificationDispatcher.format_slack_payload(
        title="CPU Crítica",
        message="Uso de CPU al 95%",
        severity="CRITICAL",
        host_info="Host #1"
    )
    assert "text" in payload
    assert "attachments" in payload
    assert payload["attachments"][0]["color"] == "#ef4444"


@pytest.mark.asyncio
async def test_notification_dispatcher_teams_payload():
    """Test formatting Teams webhook payloads."""
    from backend.app.notifications_dispatcher import NotificationDispatcher
    payload = NotificationDispatcher.format_teams_payload(
        title="Disco Lleno",
        message="Disco C: al 92%",
        severity="HIGH",
        host_info="Host #2"
    )
    assert payload["@type"] == "MessageCard"
    assert payload["themeColor"] == "F97316"
