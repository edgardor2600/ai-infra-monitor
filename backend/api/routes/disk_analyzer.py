"""
Disk Analyzer API Routes

This module provides endpoints for disk analysis and cleanup operations.
"""

import os
import json
import logging
import psycopg2
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from dotenv import load_dotenv
from datetime import datetime

from backend.api.models.disk_analyzer import (
    ScanRequest,
    ScanResponse,
    CleanupRequest,
    CleanupResponse,
    ScanListResponse,
    CleanupListResponse,
    RollbackRequest,
    RollbackResponse
)
from backend.disk_analyzer.scanner import DiskScanner
from backend.disk_analyzer.cleaner import DiskCleaner

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["disk_analyzer"], prefix="/disk-analyzer")


def get_db_connection():
    """
    Create a database connection using environment variables.
    
    Returns:
        psycopg2.connection: Database connection object
    
    Raises:
        HTTPException: If connection fails
    """
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        return conn
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed"
        )


def perform_scan_task(scan_id: int, host_id: int):
    """
    Background task to perform disk scan.
    
    Args:
        scan_id: ID of the scan record
        host_id: ID of the host to scan
    """
    conn = None
    try:
        logger.info(f"Starting background scan task for scan_id={scan_id}, host_id={host_id}")
        
        # Update scan status to running
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE disk_scans SET status = 'running' WHERE id = %s",
            (scan_id,)
        )
        conn.commit()
        
        # Perform scan
        scanner = DiskScanner(host_id)
        scan_results = scanner.scan_all_categories()
        
        # Prepare categories data with disk_info
        categories_with_disk_info = scan_results['categories'].copy()
        categories_with_disk_info['disk_info'] = scan_results.get('disk_info', {})
        
        # Store results in database
        cursor.execute(
            """
            UPDATE disk_scans 
            SET status = 'completed',
                total_size_bytes = %s,
                categories = %s,
                completed_at = NOW()
            WHERE id = %s
            """,
            (
                scan_results['total_size'],
                json.dumps(categories_with_disk_info),
                scan_id
            )
        )
        conn.commit()
        
        # Store individual cleanup items
        for category_name, category_data in scan_results['categories'].items():
            for file_info in category_data.get('files', []):
                cursor.execute(
                    """
                    INSERT INTO cleanup_items 
                    (scan_id, category, file_path, file_size_bytes, last_accessed, is_safe, risk_level)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        scan_id,
                        category_name,
                        file_info['path'],
                        file_info['size'],
                        file_info.get('last_accessed'),
                        file_info.get('is_safe', True),
                        file_info.get('risk_level', 'low')
                    )
                )
        
        conn.commit()
        cursor.close()
        
        logger.info(f"Scan completed successfully for scan_id={scan_id}")
        
    except Exception as e:
        logger.error(f"Error in scan task: {e}")
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE disk_scans 
                SET status = 'failed', error_message = %s, completed_at = NOW()
                WHERE id = %s
                """,
                (str(e), scan_id)
            )
            conn.commit()
            cursor.close()
    finally:
        if conn:
            conn.close()


@router.post("/scan", response_model=dict)
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """
    Start a disk scan for a host.
    
    This endpoint creates a scan record and starts the scan in the background.
    
    Args:
        request: ScanRequest with host_id
        background_tasks: FastAPI background tasks
    
    Returns:
        dict: Response with scan_id and status
    """
    logger.info(f"Starting disk scan for host_id={request.host_id}")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create scan record
        cursor.execute(
            """
            INSERT INTO disk_scans (host_id, status, started_at)
            VALUES (%s, 'pending', NOW())
            RETURNING id
            """,
            (request.host_id,)
        )
        
        scan_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        
        # Start scan in background
        background_tasks.add_task(perform_scan_task, scan_id, request.host_id)
        
        logger.info(f"Created scan record with id={scan_id}")
        
        return {
            "ok": True,
            "scan_id": scan_id,
            "status": "pending",
            "message": "Scan started in background"
        }
        
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start scan"
        )
    finally:
        if conn:
            conn.close()


@router.get("/scan/{scan_id}", response_model=dict)
async def get_scan(scan_id: int):
    """
    Get scan results by ID.
    
    Args:
        scan_id: ID of the scan
    
    Returns:
        dict: Scan results
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT id, host_id, status, total_size_bytes, categories, 
                   recommendations, error_message, started_at, completed_at
            FROM disk_scans
            WHERE id = %s
            """,
            (scan_id,)
        )
        
        row = cursor.fetchone()
        cursor.close()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scan {scan_id} not found"
            )
        
        categories_data = row[4] if row[4] else {}
        
        # Extract disk_info if it exists in categories (stored during scan)
        disk_info = categories_data.pop('disk_info', None) if isinstance(categories_data, dict) else None
        
        return {
            "scan_id": row[0],
            "host_id": row[1],
            "status": row[2],
            "total_size": row[3],
            "categories": categories_data,
            "disk_info": disk_info,
            "recommendations": row[5] if row[5] else {},
            "error_message": row[6],
            "started_at": row[7].isoformat() if row[7] else None,
            "completed_at": row[8].isoformat() if row[8] else None
        }
        
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve scan"
        )
    finally:
        if conn:
            conn.close()


@router.get("/scans", response_model=dict)
async def list_scans(host_id: int = None, limit: int = 10):
    """
    List all scans, optionally filtered by host.
    
    Args:
        host_id: Optional host ID to filter by
        limit: Maximum number of scans to return
    
    Returns:
        dict: List of scans
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if host_id:
            cursor.execute(
                """
                SELECT id, host_id, status, total_size_bytes, started_at, completed_at
                FROM disk_scans
                WHERE host_id = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (host_id, limit)
            )
        else:
            cursor.execute(
                """
                SELECT id, host_id, status, total_size_bytes, started_at, completed_at
                FROM disk_scans
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (limit,)
            )
        
        rows = cursor.fetchall()
        cursor.close()
        
        scans = []
        for row in rows:
            scans.append({
                "scan_id": row[0],
                "host_id": row[1],
                "status": row[2],
                "total_size": row[3],
                "started_at": row[4].isoformat() if row[4] else None,
                "completed_at": row[5].isoformat() if row[5] else None
            })
        
        return {
            "scans": scans,
            "total": len(scans)
        }
        
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list scans"
        )
    finally:
        if conn:
            conn.close()


@router.post("/cleanup", response_model=dict)
async def perform_cleanup(request: CleanupRequest):
    """
    Perform cleanup for selected categories.
    
    Args:
        request: CleanupRequest with scan_id, categories, and backup option
    
    Returns:
        dict: Cleanup results
    """
    logger.info(f"Starting cleanup for scan_id={request.scan_id}, categories={request.categories}")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get scan data
        cursor.execute(
            "SELECT host_id, categories FROM disk_scans WHERE id = %s",
            (request.scan_id,)
        )
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scan {request.scan_id} not found"
            )
        
        host_id = row[0]
        categories_data = row[1] if row[1] else {}
        
        # Transform categories_data to extract files for cleanup
        # categories_data has structure: {category_name: {files: [...], total_size: ..., ...}}
        # cleaner expects: {category_name: [files]}
        files_by_category = {}
        for category_name in request.categories:
            if category_name in categories_data:
                files_by_category[category_name] = categories_data[category_name].get('files', [])
            else:
                logger.warning(f"Category {category_name} not found in scan data")
                files_by_category[category_name] = []
        
        logger.info(f"Prepared {len(files_by_category)} categories for cleanup")
        for cat_name, files in files_by_category.items():
            logger.info(f"  {cat_name}: {len(files)} files")
        
        # Create cleanup operation record
        cursor.execute(
            """
            INSERT INTO cleanup_operations 
            (scan_id, host_id, status, categories_cleaned, started_at)
            VALUES (%s, %s, 'running', %s, NOW())
            RETURNING id
            """,
            (request.scan_id, host_id, request.categories)
        )
        
        operation_id = cursor.fetchone()[0]
        conn.commit()
        
        # Perform cleanup
        cleaner = DiskCleaner(host_id, request.scan_id)
        cleanup_results = cleaner.cleanup_categories(
            request.categories,
            files_by_category,
            request.create_backup
        )
        
        # Update cleanup operation
        cursor.execute(
            """
            UPDATE cleanup_operations
            SET status = 'completed',
                total_files_deleted = %s,
                total_size_freed_bytes = %s,
                backup_path = %s,
                completed_at = NOW()
            WHERE id = %s
            """,
            (
                cleanup_results['files_deleted'],
                cleanup_results['size_freed'],
                cleanup_results.get('backup_path'),
                operation_id
            )
        )
        
        conn.commit()
        cursor.close()
        
        logger.info(f"Cleanup completed for operation_id={operation_id}")
        
        return {
            "ok": True,
            "operation_id": operation_id,
            "files_deleted": cleanup_results['files_deleted'],
            "size_freed": cleanup_results['size_freed'],
            "backup_path": cleanup_results.get('backup_path'),
            "errors": cleanup_results.get('errors', [])
        }
        
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform cleanup"
        )
    finally:
        if conn:
            conn.close()


@router.get("/cleanups", response_model=dict)
async def list_cleanups(scan_id: int = None, limit: int = 10):
    """
    List cleanup operations.
    
    Args:
        scan_id: Optional scan ID to filter by
        limit: Maximum number of operations to return
    
    Returns:
        dict: List of cleanup operations
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if scan_id:
            cursor.execute(
                """
                SELECT id, scan_id, host_id, status, categories_cleaned,
                       total_files_deleted, total_size_freed_bytes, backup_path,
                       started_at, completed_at
                FROM cleanup_operations
                WHERE scan_id = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (scan_id, limit)
            )
        else:
            cursor.execute(
                """
                SELECT id, scan_id, host_id, status, categories_cleaned,
                       total_files_deleted, total_size_freed_bytes, backup_path,
                       started_at, completed_at
                FROM cleanup_operations
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (limit,)
            )
        
        rows = cursor.fetchall()
        cursor.close()
        
        operations = []
        for row in rows:
            operations.append({
                "operation_id": row[0],
                "scan_id": row[1],
                "host_id": row[2],
                "status": row[3],
                "categories_cleaned": row[4],
                "files_deleted": row[5],
                "size_freed": row[6],
                "backup_path": row[7],
                "started_at": row[8].isoformat() if row[8] else None,
                "completed_at": row[9].isoformat() if row[9] else None
            })
        
        return {
            "operations": operations,
            "total": len(operations)
        }
        
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list cleanup operations"
        )
    finally:
        if conn:
            conn.close()


@router.post("/rollback", response_model=dict)
async def perform_rollback(request: RollbackRequest):
    """
    Rollback a cleanup operation by restoring files from backup.
    
    Args:
        request: RollbackRequest with operation_id
    
    Returns:
        dict: Rollback results
    """
    logger.info(f"Starting rollback for operation_id={request.operation_id}")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get cleanup operation data
        cursor.execute(
            """
            SELECT host_id, scan_id, backup_path, status
            FROM cleanup_operations
            WHERE id = %s
            """,
            (request.operation_id,)
        )
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cleanup operation {request.operation_id} not found"
            )
        
        host_id, scan_id, backup_path, status_val = row
        
        if not backup_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No backup available for this cleanup operation"
            )
        
        # Perform rollback
        cleaner = DiskCleaner(host_id, scan_id)
        cleaner.backup_path = backup_path
        
        rollback_results = cleaner.rollback(request.operation_id)
        
        cursor.close()
        
        logger.info(f"Rollback completed for operation_id={request.operation_id}")
        
        return {
            "ok": True,
            "operation_id": request.operation_id,
            "files_restored": rollback_results['files_restored'],
            "errors": rollback_results.get('errors', [])
        }
        
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform rollback"
        )
    finally:
        if conn:
            conn.close()
