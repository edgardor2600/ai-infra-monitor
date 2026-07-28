"""
Tests for 90% Disk Occupancy Unattended Auto-Remediator Engine.
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.disk_analyzer.auto_remediator import AutoRemediator


@pytest.mark.asyncio
async def test_auto_remediation_threshold_check():
    """Test that AutoRemediator skips if disk occupancy is below 90%."""
    res = await AutoRemediator.check_and_execute(host_id=1, org_id=1, current_disk_percent=85.0)
    assert res["triggered"] is False
    assert "below 90% threshold" in res["reason"]


@pytest.mark.asyncio
async def test_auto_remediation_execution():
    """Test AutoRemediator execution when disk >= 90%."""
    mock_scan_res = {
        "categories": {
            "temp_files": {"files": [{"path": "C:\\temp\\t1.tmp", "size": 1024}]},
            "browser_cache": {"files": [{"path": "C:\\cache\\c1.bin", "size": 2048}]},
            "recycle_bin": {"files": []}
        }
    }
    mock_cleanup_res = {
        "files_deleted_count": 2,
        "total_bytes_freed": 3072,
        "backup_path": "C:\\backup\\auto_1"
    }

    with patch("backend.disk_analyzer.auto_remediator.NotificationDispatcher.get_org_settings") as mock_set, \
         patch("backend.disk_analyzer.auto_remediator.get_db_connection") as mock_db, \
         patch("backend.disk_analyzer.auto_remediator.DiskScanner.scan_all_categories", return_value=mock_scan_res), \
         patch("backend.disk_analyzer.auto_remediator.DiskCleaner.cleanup_categories", return_value=mock_cleanup_res), \
         patch("backend.disk_analyzer.auto_remediator.NotificationDispatcher.send_webhook") as mock_hook:

        mock_set.return_value = {"auto_remediation_enabled": True, "webhook_url": "https://hooks.slack.com/test"}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None # No recent execution
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        res = await AutoRemediator.check_and_execute(host_id=1, org_id=1, current_disk_percent=92.5)

        assert res["triggered"] is True
        assert res["files_deleted"] == 2
        assert res["bytes_freed"] == 3072
        assert mock_hook.called is True
