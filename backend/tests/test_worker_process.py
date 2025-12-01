"""
Tests for worker process_host function
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from backend.worker.worker import process_host, create_alert


@pytest.mark.asyncio
async def test_create_alert():
    """
    Test that create_alert inserts an alert into the database
    """
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [123]  # Alert ID
    mock_conn.cursor.return_value = mock_cursor
    
    # Call create_alert
    alert_id = await create_alert(
        mock_conn,
        host_id=1,
        metric_name="cpu_percent",
        severity="HIGH",
        message="Test alert"
    )
    
    # Verify alert was created
    assert alert_id == 123
    
    # Verify SQL was executed
    mock_cursor.execute.assert_called_once()
    sql_call = mock_cursor.execute.call_args[0][0]
    assert "INSERT INTO alerts" in sql_call
    assert "host_id" in sql_call
    assert "metric_name" in sql_call
    assert "severity" in sql_call
    assert "message" in sql_call
    
    # Verify parameters
    params = mock_cursor.execute.call_args[0][1]
    assert params == (1, "cpu_percent", "HIGH", "Test alert")
    
    # Verify commit was called
    mock_conn.commit.assert_called_once()


@pytest.mark.asyncio
async def test_process_host_creates_alert_high_cpu():
    """
    Test that process_host creates alert when CPU is over 90%
    
    Mock db responses with synthetic series where avg_30 > 90
    """
    # Mock database connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    
    # Mock metrics query responses
    # First query (30s): return CPU values averaging > 90
    cpu_values_30s = [(95.0,), (92.0,), (94.0,)]  # avg = 93.67
    
    # Second query (60s): return CPU values averaging lower
    cpu_values_60s = [(95.0,), (92.0,), (94.0,), (50.0,), (50.0,), (50.0,)]  # avg = 71.83
    
    # Mock cursor.fetchall() to return different values for each call
    mock_cursor.fetchall.side_effect = [cpu_values_30s, cpu_values_60s]
    
    # Mock cursor for alert insertion
    mock_cursor.fetchone.return_value = [456]  # Alert ID
    
    mock_conn.cursor.return_value = mock_cursor
    
    # Call process_host
    alerts = await process_host(1, mock_conn)
    
    # Verify at least one alert was created (HIGH severity for CPU > 90)
    assert len(alerts) >= 1
    assert 456 in alerts
    
    # Verify database queries were made
    assert mock_cursor.execute.call_count >= 2  # At least 2 SELECT queries


@pytest.mark.asyncio
async def test_process_host_creates_alert_cpu_delta():
    """
    Test that process_host creates alert when CPU delta > 200%
    
    Mock db responses where avg_30 is much higher than avg_60
    """
    # Mock database connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    
    # Mock metrics query responses
    # First query (30s): high CPU values
    cpu_values_30s = [(90.0,), (90.0,)]  # avg = 90
    
    # Second query (60s): low CPU values
    cpu_values_60s = [(90.0,), (90.0,), (20.0,), (20.0,)]  # avg = 55
    # delta = (90 - 55) / 55 * 100 = 63.6% → no alert
    
    # Let's use values that trigger the delta rule
    cpu_values_30s = [(90.0,), (90.0,)]  # avg = 90
    cpu_values_60s = [(90.0,), (90.0,), (10.0,), (10.0,)]  # avg = 50
    # delta = (90 - 50) / 50 * 100 = 80% → no alert
    
    # Use even more extreme values
    cpu_values_30s = [(90.0,), (90.0,)]  # avg = 90
    cpu_values_60s = [(90.0,), (90.0,), (5.0,), (5.0,), (5.0,), (5.0,)]  # avg = 33.33
    # delta = (90 - 33.33) / 33.33 * 100 = 170% → no alert
    
    # Final attempt: avg_30 = 90, avg_60 = 20
    cpu_values_30s = [(90.0,), (90.0,)]  # avg = 90
    cpu_values_60s = [(90.0,), (90.0,), (5.0,), (5.0,), (5.0,), (5.0,), (5.0,), (5.0,)]  # avg = 26.25
    # delta = (90 - 26.25) / 26.25 * 100 = 242.86% → alert!
    
    mock_cursor.fetchall.side_effect = [cpu_values_30s, cpu_values_60s]
    mock_cursor.fetchone.return_value = [789]  # Alert ID
    
    mock_conn.cursor.return_value = mock_cursor
    
    # Call process_host
    alerts = await process_host(1, mock_conn)
    
    # Verify alert was created for delta
    assert len(alerts) >= 1
    assert 789 in alerts


@pytest.mark.asyncio
async def test_process_host_no_alerts():
    """
    Test that process_host does not create alerts when conditions are not met
    """
    # Mock database connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    
    # Mock metrics query responses with normal CPU values
    cpu_values_30s = [(50.0,), (55.0,), (52.0,)]  # avg = 52.33
    cpu_values_60s = [(50.0,), (55.0,), (52.0,), (48.0,), (50.0,)]  # avg = 51.0
    
    mock_cursor.fetchall.side_effect = [cpu_values_30s, cpu_values_60s]
    mock_conn.cursor.return_value = mock_cursor
    
    # Call process_host
    alerts = await process_host(1, mock_conn)
    
    # Verify no alerts were created
    assert len(alerts) == 0
