"""
Tests for Scheduled Disk Maintenance (Cron Jobs) and zero-risk background runner.
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.worker.scheduled_cleanup_runner import SAFE_AUTOMATED_CATEGORIES, run_due_scheduled_cleanups


def test_safe_automated_categories_enforcement():
    """Verify that automated scheduled maintenance only allows zero-risk categories."""
    assert "temp_files" in SAFE_AUTOMATED_CATEGORIES
    assert "browser_cache" in SAFE_AUTOMATED_CATEGORIES
    assert "recycle_bin" in SAFE_AUTOMATED_CATEGORIES
    assert "dev_cache" not in SAFE_AUTOMATED_CATEGORIES
    assert "developer_artifacts" not in SAFE_AUTOMATED_CATEGORIES


@pytest.mark.asyncio
async def test_run_due_scheduled_cleanups_mocked():
    """Verify scheduled cleanup runner queries due jobs and executes safe cleanups."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    
    # Mock schedules query return: 1 schedule due for host 1
    mock_schedules = [
        (1, 1, 1, ['temp_files', 'dev_cache'], 24, None, None)
    ]
    mock_cursor.fetchall.return_value = mock_schedules
    mock_conn.cursor.return_value = mock_cursor

    mock_scan_res = {
        'categories': {
            'temp_files': {'files': [{'path': '/tmp/test.tmp', 'size': 100}]}
        }
    }

    mock_cleanup_res = {
        'files_deleted': 1,
        'size_freed': 100,
        'backup_path': '/backup/test'
    }

    with patch('backend.worker.scheduled_cleanup_runner.get_db_connection', return_value=mock_conn), \
         patch('backend.disk_analyzer.scanner.DiskScanner.scan_all_categories', return_value=mock_scan_res), \
         patch('backend.disk_analyzer.cleaner.DiskCleaner.cleanup_categories', return_value=mock_cleanup_res):

        res = run_due_scheduled_cleanups()

        assert len(res) == 1
        assert res[0]["schedule_id"] == 1
        assert res[0]["host_id"] == 1
        assert res[0]["files_deleted"] == 1
        # dev_cache should be filtered out from automatic background run
        assert "dev_cache" not in res[0]["categories_cleaned"]
        assert "temp_files" in res[0]["categories_cleaned"]
