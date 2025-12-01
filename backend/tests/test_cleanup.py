"""
Tests for data cleanup script
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
from backend.scripts.cleanup_data import cleanup_metrics

@pytest.fixture
def mock_conn():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn

def test_cleanup_metrics_dry_run(mock_conn):
    """Test cleanup in dry-run mode (should only count)"""
    cursor = mock_conn.cursor.return_value
    cursor.fetchone.return_value = [100]
    
    count = cleanup_metrics(mock_conn, days=7, dry_run=True)
    
    assert count == 100
    # Should execute SELECT COUNT, not DELETE
    assert "SELECT COUNT(*)" in cursor.execute.call_args[0][0]
    assert "DELETE" not in cursor.execute.call_args[0][0]
    # Should not commit
    mock_conn.commit.assert_not_called()

def test_cleanup_metrics_execution(mock_conn):
    """Test cleanup execution (should delete)"""
    cursor = mock_conn.cursor.return_value
    cursor.rowcount = 50
    
    count = cleanup_metrics(mock_conn, days=7, dry_run=False)
    
    assert count == 50
    # Should execute DELETE
    assert "DELETE FROM metrics_raw" in cursor.execute.call_args[0][0]
    # Should commit
    mock_conn.commit.assert_called_once()

def test_cleanup_cutoff_calculation(mock_conn):
    """Test that cutoff date is calculated correctly"""
    cursor = mock_conn.cursor.return_value
    
    cleanup_metrics(mock_conn, days=1, dry_run=False)
    
    # Extract the date passed to execute
    args = cursor.execute.call_args[0]
    cutoff_param = args[1][0]
    
    # Verify it's roughly 24 hours ago
    now = datetime.now(timezone.utc)
    expected = now - timedelta(days=1)
    
    # Allow small time difference (execution time)
    diff = abs((expected - cutoff_param).total_seconds())
    assert diff < 5  # Should be within 5 seconds
