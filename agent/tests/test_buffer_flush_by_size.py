"""
Tests for buffer flush by size logic
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio
from agent.run import run


@pytest.mark.asyncio
async def test_buffer_flush_by_size():
    """
    Test that buffer flushes when it reaches AGENT_BATCH_MAX size.
    
    Mock psutil to return fixed values and set AGENT_BATCH_MAX to 3.
    Verify that send_batch is called when buffer reaches 3 samples.
    """
    # Mock environment variables
    with patch.dict('os.environ', {
        'AGENT_INTERVAL': '0.1',  # Fast interval for testing
        'AGENT_BATCH_MAX': '3',  # Small batch size
        'AGENT_BATCH_TIMEOUT': '100',  # Large timeout so it doesn't trigger
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
                        await asyncio.sleep(0.5)  # Let it run for 0.5 seconds
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    
                    await run_for_time()
                    
                    # Verify send_batch was called at least once
                    assert mock_send.call_count >= 1, "send_batch should be called when buffer reaches batch_max"
                    
                    # Verify the batch structure
                    call_args = mock_send.call_args_list[0]
                    batch = call_args[0][0]  # First positional argument
                    
                    assert "host_id" in batch
                    assert batch["host_id"] == 1
                    assert "timestamp" in batch
                    assert "interval" in batch
                    assert "samples" in batch
                    
                    # Since collect_once returns 2 samples (cpu and mem),
                    # and batch_max is 3, we need at least 2 collections
                    # First collection: 2 samples (buffer = 2)
                    # Second collection: 2 samples (buffer = 4, triggers flush at 3)
                    # So the first batch should have at least 3 samples
                    assert len(batch["samples"]) >= 3, f"Expected at least 3 samples, got {len(batch['samples'])}"
