"""
Tests for Analysis Worker
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.worker.analysis_worker import process_job

@pytest.mark.asyncio
async def test_process_job_success():
    """Test that process_job calls LLM and saves to DB."""
    
    # Mock data
    job_data = {
        "job_id": "test-job",
        "alert_id": 1,
        "summary": "Test Alert"
    }
    
    llm_result = {"summary": "Result", "confidence": 0.9}
    
    # Mock LLM Adapter
    mock_adapter = MagicMock()
    mock_adapter.analyze = AsyncMock(return_value=llm_result)
    
    # Mock DB connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [100] # analysis_id
    mock_conn.cursor.return_value = mock_cursor
    
    with patch("backend.worker.analysis_worker.get_db_connection", return_value=mock_conn):
        await process_job(job_data, mock_adapter)
        
        # Verify LLM called
        mock_adapter.analyze.assert_called_once_with("Test Alert")
        
        # Verify DB insert
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO analyses" in sql
        
        # Verify commit
        mock_conn.commit.assert_called_once()
