"""
Pydantic Models for Ingest API

This module defines the data models for the metrics ingestion endpoint.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional


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


class ProcessSample(BaseModel):
    """
    A single process metric sample.
    
    Attributes:
        name: Name of the process (e.g., "chrome.exe", "python.exe")
        pid: Process ID
        cpu_percent: CPU usage percentage
        memory_mb: Memory usage in megabytes
        status: Process status (e.g., "running", "sleeping")
    """
    name: str = Field(..., min_length=1, description="Process name")
    pid: int = Field(..., ge=0, description="Process ID")
    cpu_percent: float = Field(..., ge=0.0, description="CPU usage percentage")
    memory_mb: float = Field(..., ge=0.0, description="Memory usage in MB")
    status: str = Field(default="unknown", min_length=1, description="Process status")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "chrome.exe",
                    "pid": 1234,
                    "cpu_percent": 15.5,
                    "memory_mb": 512.3,
                    "status": "running"
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
        processes: Optional list of process metric samples
    """
    host_id: int = Field(..., gt=0, description="Host ID")
    timestamp: datetime = Field(..., description="Collection timestamp")
    interval: int = Field(..., gt=0, description="Collection interval in seconds")
    samples: List[Sample] = Field(..., min_length=1, description="List of metric samples")
    processes: Optional[List[ProcessSample]] = Field(None, description="Optional list of process metrics")
    
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
                    ],
                    "processes": [
                        {
                            "name": "chrome.exe",
                            "pid": 1234,
                            "cpu_percent": 15.5,
                            "memory_mb": 512.3,
                            "status": "running"
                        }
                    ]
                }
            ]
        }
    }

