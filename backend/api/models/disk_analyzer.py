"""
Disk Analyzer API Models

Pydantic models for disk analyzer API endpoints.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime


class ScanRequest(BaseModel):
    """Request to start a disk scan"""
    host_id: int = Field(..., description="ID of the host to scan")


class CategoryInfo(BaseModel):
    """Information about a cleanup category"""
    name: str
    display_name: str
    description: str
    risk_level: str
    is_safe_auto: bool
    file_count: int
    total_size: int
    files: List[Dict] = Field(default_factory=list)


class ScanResponse(BaseModel):
    """Response from a disk scan"""
    scan_id: int
    host_id: int
    status: str
    categories: Dict[str, CategoryInfo]
    total_size: int
    total_files: int
    recommendations: Optional[Dict] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class CleanupRequest(BaseModel):
    """Request to perform cleanup"""
    scan_id: int = Field(..., description="ID of the scan to clean")
    categories: List[str] = Field(..., description="List of category names to clean")
    create_backup: bool = Field(default=True, description="Whether to create backup before cleanup")


class CleanupResponse(BaseModel):
    """Response from a cleanup operation"""
    operation_id: int
    scan_id: int
    status: str
    files_deleted: int
    size_freed: int
    backup_path: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: Optional[datetime] = None


class ScanListResponse(BaseModel):
    """Response listing all scans"""
    scans: List[Dict]
    total: int


class CleanupListResponse(BaseModel):
    """Response listing all cleanup operations"""
    operations: List[Dict]
    total: int


class RollbackRequest(BaseModel):
    """Request to rollback a cleanup operation"""
    operation_id: int = Field(..., description="ID of the cleanup operation to rollback")


class RollbackResponse(BaseModel):
    """Response from a rollback operation"""
    operation_id: int
    status: str
    files_restored: int
    errors: List[str] = Field(default_factory=list)
