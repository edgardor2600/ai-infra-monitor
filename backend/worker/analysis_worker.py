"""
AI Infra Monitor - Analysis Worker

This worker processes analysis jobs from Redis queue.
"""

import os
import sys
import json
import time
import asyncio
import logging
import redis
import psycopg2
from dotenv import load_dotenv

# Add parent directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from backend.app.llm_adapter import LLMAdapter

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Redis connection
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True
)

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

async def process_job(job_data: dict, llm_adapter: LLMAdapter):
    """Process a single analysis job."""
    alert_id = job_data["alert_id"]
    summary = job_data["summary"]
    job_id = job_data["job_id"]
    
    logger.info(f"Processing job {job_id} for alert {alert_id}")
    
    # Call LLM
    result = await llm_adapter.analyze(summary)
    
    # Save to DB
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO analyses (host_id, alert_id, result, created_at)
            SELECT host_id, %s, %s, NOW()
            FROM alerts WHERE id = %s
            RETURNING id
            """,
            (alert_id, json.dumps(result), alert_id)
        )
        analysis_id = cursor.fetchone()[0]
        conn.commit()
        logger.info(f"Analysis saved with ID {analysis_id}")
        
    except Exception as e:
        logger.error(f"Failed to save analysis: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

async def worker_loop():
    """Main worker loop."""
    logger.info("Analysis Worker started...")
    
    # Initialize LLM Adapter
    model_name = os.getenv("LLM_MODEL", "mistral:7b")
    llm_adapter = LLMAdapter(redis_client, model_name=model_name)
    
    while True:
        try:
            # Blocking pop from Redis (timeout 5s to allow clean shutdown check)
            # blpop returns (key, value) tuple or None
            item = redis_client.blpop("analysis_queue", timeout=5)
            
            if item:
                _, payload = item
                job_data = json.loads(payload)
                await process_job(job_data, llm_adapter)
                
        except Exception as e:
            logger.error(f"Worker error: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
