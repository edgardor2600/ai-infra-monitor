"""
Tests for worker notifications
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from backend.worker.notifications import log_alert
from backend.worker.worker import create_alert


def test_log_alert_format(capsys):
    """
    Test that log_alert prints the correct JSON format
    """
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
    
    # Verify it's valid JSON after the prefix
    json_str = output.replace("ALERT CREATED ", "").strip()
    parsed = json.loads(json_str)
    assert parsed["id"] == 123


@pytest.mark.asyncio
async def test_create_alert_calls_notification():
    """
    Test that create_alert calls log_alert
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [999]
    mock_conn.cursor.return_value = mock_cursor
    
    with patch("backend.worker.notifications.log_alert") as mock_log:
        await create_alert(
            mock_conn,
            host_id=1,
            metric_name="cpu_percent",
            severity="HIGH",
            message="Test alert"
        )
        
        mock_log.assert_called_once()
        call_args = mock_log.call_args[0][0]
        assert call_args["id"] == 999
        assert call_args["severity"] == "HIGH"
