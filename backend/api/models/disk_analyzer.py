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
    drive: Optional[str] = Field("C:", description="Target drive letter to scan (e.g. C:, D:)")


class AgentScanPayload(BaseModel):
    """Payload for real local disk scan results sent directly from agent"""
    host_id: int = Field(..., description="Host ID sending scan results")
    org_id: int = Field(1, description="Organization ID")
    drive: str = Field("C:", description="Target drive letter")
    total_size_bytes: int = Field(..., description="Total size in bytes")
    disk_info: Optional[Dict] = Field(None, description="Global disk capacity info (total, used, free, percent_used)")
    categories: Dict[str, Dict] = Field(..., description="Scan categories with files and sizes")


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
    drive: Optional[str] = "C:"
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


class RollbackRequest(BaseModel):
    """Request to rollback a cleanup operation"""
    operation_id: int = Field(..., description="ID of the cleanup operation to rollback")


class PurgeBackupRequest(BaseModel):
    """Request to purge a backup folder to free disk space."""
    backup_path: str = Field(..., description="Absolute path of the backup directory to purge")


class AIAnalysisRequest(BaseModel):
    """Request to analyze scan with MiniMax AI."""
    scan_id: int = Field(..., description="ID of the completed scan to analyze")


class DuplicateScanRequest(BaseModel):
    """Request to scan for duplicate files by SHA-256."""
    target_path: str = Field(..., description="Directory path to scan for duplicate files")
    min_size_mb: int = Field(default=1, description="Minimum file size in MB to check for duplicates")


class ExportReportRequest(BaseModel):
    """Request to export disk diagnostic report as JSON or PDF."""
    scan_id: int = Field(..., description="ID of the scan to export")
    format: str = Field(default="json", description="Export format: json or pdf")


class ActivateLicenseRequest(BaseModel):
    """Request to activate a B2B License Key."""
    license_key: str = Field(..., description="License Key string to validate and activate")


class CreateScheduledCleanupRequest(BaseModel):
    """Request to create or update an automated scheduled maintenance job."""
    host_id: int = Field(..., description="ID of the target host")
    interval_hours: int = Field(default=24, description="Schedule interval in hours (default 24)")
    categories: List[str] = Field(
        default=["temp_files", "browser_cache", "recycle_bin"],
        description="Zero-risk categories for automatic maintenance"
    )
    enabled: bool = Field(default=True, description="Whether schedule is active")



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

