"""
Pydantic Models for Ingest API

This module defines the data models for the metrics ingestion endpoint.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import List


class Sample(BaseModel):
    """
    A single metric sample.
    
    Attributes:
        metric: Name of the metric (e.g., "cpu_usage", "memory_used")
        value: Numeric value of the metric
    """
    metric: str = Field(..., min_length=1, description="Metric name")
    value: float = Field(..., description="Metric value")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "metric": "cpu_usage",
                    "value": 45.2
                }
            ]
        }
    }


class IngestBatch(BaseModel):
    """
    A batch of metric samples from a host.
    
    Attributes:
        host_id: ID of the host sending metrics
        timestamp: Timestamp when metrics were collected
        interval: Collection interval in seconds
        samples: List of metric samples
    """
    host_id: int = Field(..., gt=0, description="Host ID")
    timestamp: datetime = Field(..., description="Collection timestamp")
    interval: int = Field(..., gt=0, description="Collection interval in seconds")
    samples: List[Sample] = Field(..., min_length=1, description="List of metric samples")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "host_id": 1,
                    "timestamp": "2025-12-01T12:00:00Z",
                    "interval": 60,
                    "samples": [
                        {"metric": "cpu_usage", "value": 45.2},
                        {"metric": "memory_used", "value": 8192.0}
                    ]
                }
            ]
        }
    }
