"""
Tests for send_batch functionality
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
from agent.sender import send_batch


@pytest.mark.asyncio
async def test_send_batch_success():
    """
    Test that send_batch correctly constructs and sends HTTP POST request.
    
    Mock httpx.AsyncClient and validate the request structure.
    """
    # Sample batch data
    batch = {
        "host_id": 1,
        "timestamp": "2025-12-01T10:00:00",
        "interval": 5,
        "samples": [
            {"metric": "cpu_percent", "value": 45.5},
            {"metric": "mem_percent", "value": 60.2}
        ]
    }
    
    backend_url = "http://test-backend"
    expected_endpoint = f"{backend_url}/api/v1/ingest/metrics"
    
    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"status": "ok", "received": 2})
    mock_response.raise_for_status = MagicMock()
    
    # Mock AsyncClient
    with patch('agent.sender.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client
        
        # Call send_batch
        result = await send_batch(batch, backend_url)
        
        # Verify the result
        assert result == {"status": "ok", "received": 2}
        
        # Verify AsyncClient was created with timeout
        mock_client_class.assert_called_once_with(timeout=10.0)
        
        # Verify POST was called with correct endpoint and data
        mock_client.post.assert_called_once_with(expected_endpoint, json=batch)
        
        # Verify raise_for_status was called
        mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_send_batch_retry_on_error():
    """
    Test that send_batch retries on HTTP errors.
    """
    batch = {
        "host_id": 1,
        "timestamp": "2025-12-01T10:00:00",
        "interval": 5,
        "samples": [{"metric": "cpu_percent", "value": 45.5}]
    }
    
    backend_url = "http://test-backend"
    
    # Mock response that fails twice then succeeds
    call_count = 0
    
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        mock_response = MagicMock()
        
        if call_count < 3:
            # First two calls fail
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server error", 
                request=MagicMock(), 
                response=mock_response
            )
        else:
            # Third call succeeds
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value={"status": "ok"})
            mock_response.raise_for_status = MagicMock()
        
        return mock_response
    
    # Mock AsyncClient
    with patch('agent.sender.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client
        
        # Call send_batch
        result = await send_batch(batch, backend_url)
        
        # Verify it eventually succeeded
        assert result == {"status": "ok"}
        
        # Verify it retried (3 calls total)
        assert call_count == 3


@pytest.mark.asyncio
async def test_send_batch_max_retries_exceeded():
    """
    Test that send_batch raises exception after max retries.
    """
    batch = {
        "host_id": 1,
        "timestamp": "2025-12-01T10:00:00",
        "interval": 5,
        "samples": [{"metric": "cpu_percent", "value": 45.5}]
    }
    
    backend_url = "http://test-backend"
    
    # Mock response that always fails
    async def mock_post(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", 
            request=MagicMock(), 
            response=mock_response
        )
        return mock_response
    
    # Mock AsyncClient
    with patch('agent.sender.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client
        
        # Call send_batch and expect it to raise
        with pytest.raises(httpx.HTTPStatusError):
            await send_batch(batch, backend_url)
