"""
AI Infra Monitor - Analysis Endpoint

This module defines the API endpoint for triggering alert analysis.
"""

import json
import uuid
import redis
import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor

router = APIRouter()

# Redis connection
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True
)

def get_db_connection():
    """Create a database connection."""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

class AnalysisResponse(BaseModel):
    job_id: str

@router.post("/alerts/{alert_id}/analyze", response_model=AnalysisResponse)
async def analyze_alert(alert_id: int):
    """
    Trigger an AI analysis for a specific alert.
    
    1. Validate alert exists and is open.
    2. Enqueue job to Redis.
    3. Return job ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # 1. Fetch alert details
        cursor.execute(
            """
            SELECT id, metric_name, severity, message, created_at 
            FROM alerts 
            WHERE id = %s AND status = 'open'
            """,
            (alert_id,)
        )
        alert = cursor.fetchone()
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found or not open")
            
        # 2. Create job payload
        job_id = str(uuid.uuid4())
        summary_text = (
            f"Alert ID: {alert['id']}\n"
            f"Metric: {alert['metric_name']}\n"
            f"Severity: {alert['severity']}\n"
            f"Message: {alert['message']}\n"
            f"Time: {alert['created_at']}"
        )
        
        job_payload = {
            "job_id": job_id,
            "alert_id": alert_id,
            "summary": summary_text
        }
        
        # 3. Enqueue to Redis
        redis_client.rpush("analysis_queue", json.dumps(job_payload))
        
        return {"job_id": job_id}
        
    finally:
        cursor.close()
        conn.close()
