"""
AI Infra Monitor Agent - Run Module

This module implements the main agent loop with buffering and batching logic.
"""

import os
import asyncio
import logging
import time
import socket
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any

from agent.collector import collect_once, collect_process_metrics
from agent.sender import send_batch

logger = logging.getLogger(__name__)


async def auto_register_host(backend_url: str) -> int:
    """
    Auto-register the current host with the backend if not already registered.
    
    Args:
        backend_url: Base URL of the backend server
        
    Returns:
        int: The host_id to use for this agent
    """
    hostname = socket.gethostname()
    logger.info(f"Auto-registering host: {hostname}")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Check if host exists
            response = await client.get(f"{backend_url}/api/v1/hosts")
            response.raise_for_status()
            data = response.json()
            
            # Look for existing host with this hostname
            hosts = data.get("hosts", [])
            for host in hosts:
                if host.get("hostname") == hostname:
                    host_id = host.get("id")
                    logger.info(f"Host '{hostname}' already registered with ID: {host_id}")
                    return host_id
            
            # Host not found, need to register it
            # Since we don't have a registration endpoint, we'll use host_id=1 as fallback
            # and log a warning
            logger.warning(
                f"Host '{hostname}' not found in backend. "
                f"Please run: python backend/scripts/register_host.py"
            )
            logger.warning("Using default host_id=1 for now")
            return 1
            
        except Exception as e:
            logger.error(f"Error during auto-registration: {e}")
            logger.warning("Falling back to default host_id=1")
            return 1



async def run(dry_run: bool = False):
    """
    Main agent loop with buffer and timeout management.
    
    Reads configuration from environment variables:
    - AGENT_INTERVAL: Collection interval in seconds (default: 5)
    - AGENT_BATCH_MAX: Maximum samples before flush (default: 20)
    - AGENT_BATCH_TIMEOUT: Maximum seconds before flush (default: 20)
    - BACKEND_URL: Backend server URL (default: http://localhost:8001)
    - AGENT_HOST_ID: Host identifier (default: 1)
    
    Args:
        dry_run: If True, prints batches without sending them
    """
    # Read configuration from environment
    interval = float(os.getenv("AGENT_INTERVAL", "5"))
    batch_max = int(os.getenv("AGENT_BATCH_MAX", "20"))
    batch_timeout = float(os.getenv("AGENT_BATCH_TIMEOUT", "20"))
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    
    # Auto-register host if AGENT_HOST_ID not explicitly set
    if os.getenv("AGENT_HOST_ID"):
        host_id = int(os.getenv("AGENT_HOST_ID"))
        logger.info(f"Using explicitly configured host_id: {host_id}")
    else:
        logger.info("AGENT_HOST_ID not set, auto-detecting...")
        host_id = await auto_register_host(backend_url)
    
    logger.info(f"Agent configuration:")
    logger.info(f"  Interval: {interval}s")
    logger.info(f"  Batch max: {batch_max}")
    logger.info(f"  Batch timeout: {batch_timeout}s")
    logger.info(f"  Backend URL: {backend_url}")
    logger.info(f"  Host ID: {host_id}")
    logger.info(f"  Dry run: {dry_run}")
    
    buffer: List[Dict[str, Any]] = []
    timer_start = time.monotonic()
    iteration_count = 0  # Track iterations for process collection
    pending_processes = None  # Store processes until next flush
    
    logger.info("Starting agent loop...")
    
    try:
        while True:
            # Collect metrics
            samples = collect_once()
            
            # Add samples to buffer (collect_once returns a list)
            buffer.extend(samples)
            logger.debug(f"Buffer size: {len(buffer)}/{batch_max}")
            
            # Collect process metrics every 15 seconds (every 3 iterations at 5s interval)
            iteration_count += 1
            if iteration_count % 3 == 0:  # 3 * 5s = 15s
                pending_processes = collect_process_metrics()
                logger.info(f"Collected {len(pending_processes)} process metrics - will send with next batch")
            
            # Check flush conditions
            elapsed = time.monotonic() - timer_start
            should_flush_size = len(buffer) >= batch_max
            should_flush_timeout = elapsed >= batch_timeout
            
            if should_flush_size or should_flush_timeout:
                reason = "size" if should_flush_size else "timeout"
                logger.info(f"Flushing buffer (reason: {reason}, size: {len(buffer)})")
                
                # Create batch
                batch = {
                    "host_id": host_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "interval": interval,
                    "samples": buffer.copy()
                }
                
                # Add pending processes if available
                if pending_processes:
                    batch["processes"] = pending_processes
                    logger.info(f"Including {len(pending_processes)} process metrics in batch")
                    pending_processes = None  # Clear after sending
                
                if dry_run:
                    # In dry-run mode, just print the batch
                    import json
                    logger.info("DRY RUN - Would send batch:")
                    print(json.dumps(batch, indent=2))
                else:
                    # Send batch to backend
                    try:
                        response = await send_batch(batch, backend_url)
                        logger.info(f"Batch sent successfully: {response}")
                    except Exception as e:
                        logger.error(f"Failed to send batch: {e}")
                        # Continue running even if send fails
                
                # Clear buffer and reset timer
                buffer.clear()
                timer_start = time.monotonic()
            
            # Sleep until next collection
            await asyncio.sleep(interval)
            
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
        
        # Flush remaining buffer if any
        if buffer:
            logger.info(f"Flushing remaining {len(buffer)} samples...")
            batch = {
                "host_id": host_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "interval": interval,
                "samples": buffer
            }
            
            if dry_run:
                import json
                print(json.dumps(batch, indent=2))
            else:
                try:
                    response = await send_batch(batch, backend_url)
                    logger.info(f"Final batch sent: {response}")
                except Exception as e:
                    logger.error(f"Failed to send final batch: {e}")
    
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        raise
