"""
Tests for buffer flush by timeout logic
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio
from agent.run import run


@pytest.mark.asyncio
async def test_buffer_flush_by_timeout():
    """
    Test that buffer flushes when timeout is reached even if buffer < batch_max.
    
    Mock time.monotonic to simulate time passing and verify flush occurs.
    """
    # Mock environment variables
    with patch.dict('os.environ', {
        'AGENT_INTERVAL': '0.1',  # Fast interval for testing
        'AGENT_BATCH_MAX': '100',  # Large batch size so it doesn't trigger
        'AGENT_BATCH_TIMEOUT': '0.3',  # Small timeout (300ms)
        'BACKEND_URL': 'http://test-backend',
        'AGENT_HOST_ID': '1'
    }):
        # Mock psutil functions
        with patch('agent.collector.psutil.cpu_percent', return_value=50.0):
            with patch('agent.collector.psutil.virtual_memory') as mock_mem:
                mock_mem.return_value = MagicMock(percent=60.0)
                
                # Mock send_batch
                with patch('agent.run.send_batch', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {"status": "ok"}
                    
                    # Run agent for a short time
                    async def run_for_time():
                        task = asyncio.create_task(run(dry_run=False))
                        await asyncio.sleep(0.6)  # Let it run for 600ms (> timeout)
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    
                    await run_for_time()
                    
                    # Verify send_batch was called at least once due to timeout
                    assert mock_send.call_count >= 1, "send_batch should be called when timeout is reached"
                    
                    # Verify the batch structure
                    call_args = mock_send.call_args_list[0]
                    batch = call_args[0][0]  # First positional argument
                    
                    assert "host_id" in batch
                    assert batch["host_id"] == 1
                    assert "timestamp" in batch
                    assert "interval" in batch
                    assert "samples" in batch
                    
                    # Buffer should have some samples but less than batch_max (100)
                    assert len(batch["samples"]) > 0, "Batch should have at least some samples"
                    assert len(batch["samples"]) < 100, f"Batch should have less than batch_max samples, got {len(batch['samples'])}"
