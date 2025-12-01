"""
AI Infra Monitor Agent - Sender Module

This module handles sending metric batches to the backend via HTTP.
"""

import logging
import httpx
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def send_batch(batch: Dict[str, Any], backend_url: str) -> Dict[str, Any]:
    """
    Envía batch vía HTTP usando httpx.AsyncClient.
    POST a: f"{backend_url}/api/v1/ingest/metrics"
    
    Args:
        batch: Dictionary containing the batch data to send
        backend_url: Base URL of the backend server
        
    Returns:
        Dict[str, Any]: JSON response from the backend
        
    Raises:
        httpx.HTTPError: If the request fails after retries
    """
    endpoint = f"{backend_url}/api/v1/ingest/metrics"
    max_retries = 3
    retry_count = 0
    
    logger.info(f"Sending batch to {endpoint}")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        while retry_count < max_retries:
            try:
                response = await client.post(endpoint, json=batch)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"Batch sent successfully: {result}")
                return result
                
            except httpx.HTTPStatusError as e:
                retry_count += 1
                logger.error(
                    f"HTTP error {e.response.status_code} sending batch "
                    f"(attempt {retry_count}/{max_retries}): {e}"
                )
                
                if retry_count >= max_retries:
                    logger.error("Max retries reached, giving up")
                    raise
                    
            except httpx.RequestError as e:
                retry_count += 1
                logger.error(
                    f"Request error sending batch "
                    f"(attempt {retry_count}/{max_retries}): {e}"
                )
                
                if retry_count >= max_retries:
                    logger.error("Max retries reached, giving up")
                    raise
                    
            except Exception as e:
                logger.error(f"Unexpected error sending batch: {e}")
                raise
    
    # Should never reach here
    raise RuntimeError("Failed to send batch after all retries")
