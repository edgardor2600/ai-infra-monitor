"""
Disk Analyzer API Routes

This module provides endpoints for disk analysis and cleanup operations.
"""

import os
import json
import logging
import psycopg2
from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Header
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime
from backend.api.routes.auth import decode_jwt_token

from backend.api.models.disk_analyzer import (
    ScanRequest,
    ScanResponse,
    CleanupRequest,
    CleanupResponse,
    ScanListResponse,
    CleanupListResponse,
    RollbackRequest,
    RollbackResponse,
    PurgeBackupRequest,
    AIAnalysisRequest,
    DuplicateScanRequest,
    ExportReportRequest,
    ActivateLicenseRequest
)
from backend.disk_analyzer.scanner import DiskScanner
from backend.disk_analyzer.cleaner import DiskCleaner
from backend.disk_analyzer.duplicate_finder import DuplicateFinder
from backend.disk_analyzer.dev_cleaner import DevMediaCleaner
from backend.app.llm_adapter import LLMAdapter

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["disk_analyzer"], prefix="/disk-analyzer")


def get_current_org_id(authorization: Optional[str] = None) -> int:
    """Extract org_id from JWT token in Authorization header."""
    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.split(" ")[1]
            payload = decode_jwt_token(token)
            return payload.get("org_id", 1)
        except Exception:
            pass
    return 1


def get_db_connection():
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


@router.get("/drives", response_model=dict)
async def get_drives():
    """Get list of available disk drives and free space info."""
    drives = DiskScanner.get_available_drives()
    return {"drives": drives}


def perform_scan_task(scan_id: int, host_id: int, drive: str = "C:"):
    """
    Background task to perform disk scan.
    """
    conn = None
    try:
        logger.info(f"Starting background scan task for scan_id={scan_id}, host_id={host_id}, drive={drive}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE disk_scans SET status = 'running' WHERE id = %s",
            (scan_id,)
        )
        conn.commit()
        
        scanner = DiskScanner(host_id, drive=drive)
        scan_results = scanner.scan_all_categories()
        
        categories_with_disk_info = scan_results['categories'].copy()
        categories_with_disk_info['disk_info'] = scan_results.get('disk_info', {})
        categories_with_disk_info['drive'] = drive
        
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
        
        # Insert cleanup items
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
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks, authorization: Optional[str] = Header(None)):
    """Start a disk scan for a host and drive."""
    org_id = get_current_org_id(authorization)
    drive = request.drive or "C:"
    logger.info(f"Starting disk scan for host_id={request.host_id}, drive={drive}, org_id={org_id}")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO disk_scans (host_id, org_id, status, started_at)
            VALUES (%s, %s, 'pending', NOW())
            RETURNING id
            """,
            (request.host_id, org_id)
        )
        
        scan_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        
        background_tasks.add_task(perform_scan_task, scan_id, request.host_id, drive)
        
        return {
            "ok": True,
            "scan_id": scan_id,
            "status": "pending",
            "drive": drive,
            "message": f"Scan started in background on drive {drive}"
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


@router.post("/analyze-ai", response_model=dict)
async def analyze_scan_ai(request: AIAnalysisRequest):
    """Analyze scan results using MiniMax AI for human-friendly insights."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT categories, total_size_bytes FROM disk_scans WHERE id = %s",
            (request.scan_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="Scan not found")
            
        categories_data = row[0] if row[0] else {}
        total_size = row[1] or 0
        
        total_files = sum(cat.get('file_count', 0) for cat in categories_data.values() if isinstance(cat, dict))
        
        scan_summary = {
            "scan_id": request.scan_id,
            "total_size_bytes": total_size,
            "total_size_formatted": DiskCleaner._format_size(total_size),
            "total_files": total_files,
            "categories": {
                k: {
                    "display_name": v.get("display_name"),
                    "file_count": v.get("file_count", 0),
                    "total_size_formatted": DiskCleaner._format_size(v.get("total_size", 0)),
                    "risk_level": v.get("risk_level")
                }
                for k, v in categories_data.items() if isinstance(v, dict)
            }
        }
        
        adapter = LLMAdapter()
        ai_report = await adapter.analyze_disk_scan(scan_summary)
        
        return {
            "ok": True,
            "scan_id": request.scan_id,
            "ai_report": ai_report
        }
    except Exception as e:
        logger.error(f"Error analyzing scan with AI: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.post("/purge-backup", response_model=dict)
async def purge_backup(request: PurgeBackupRequest):
    """Purge a backup folder to immediately free disk space."""
    res = DiskCleaner.purge_backup_path(request.backup_path)
    if not res.get('success'):
        raise HTTPException(status_code=400, detail=res.get('message'))
    return res


@router.post("/inspect-backup", response_model=dict)
async def inspect_backup(request: PurgeBackupRequest):
    """Inspect backup directory contents and generate MiniMax AI analysis before purge."""
    backup_path = request.backup_path
    if not backup_path or not os.path.exists(backup_path):
        return {
            "ok": True,
            "backup_info": {
                "backup_path": backup_path,
                "total_size_bytes": 0,
                "size_formatted": "0 B (Ya eliminado)",
                "file_count": 0,
                "categories": []
            },
            "ai_analysis": {
                "title": "Respaldo No Existente",
                "freed_space_notice": "Este respaldo ya no se encuentra en el almacenamiento local.",
                "apps_and_projects_affected": [],
                "purge_consequence_es": "Puedes confirmar la eliminación para limpiar este registro del historial.",
                "safety_confirmation": "No hay archivos retenidos consumiendo espacio en esta ubicación."
            }
        }
        
    total_size = 0
    file_count = 0
    categories_found = []
    
    try:
        subitems = os.listdir(backup_path)
        for item in subitems:
            item_path = os.path.join(backup_path, item)
            if os.path.isdir(item_path):
                categories_found.append(item)
                
        for root, dirs, files in os.walk(backup_path):
            for f in files:
                file_count += 1
                fp = os.path.join(root, f)
                if os.path.isfile(fp):
                    total_size += os.path.getsize(fp)
                    
        backup_info = {
            "backup_path": backup_path,
            "total_size_bytes": total_size,
            "size_formatted": DiskCleaner._format_size(total_size),
            "file_count": file_count,
            "categories": categories_found
        }
        
        adapter = LLMAdapter()
        ai_analysis = await adapter.analyze_backup_purge(backup_info)
        
        return {
            "ok": True,
            "backup_info": backup_info,
            "ai_analysis": ai_analysis
        }
    except Exception as e:
        logger.error(f"Error inspecting backup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def check_license_permission(required_feature: str, authorization: Optional[str] = None):
    """Enforce B2B License Tier feature permissions strictly for current organization."""
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT license_tier FROM organizations WHERE id = %s;", (org_id,))
        row = cursor.fetchone()
        tier = (row[0] if row else "pro_saas").lower()
        
        feature_matrix = {
            "starter": ["basic_scan", "manual_cleanup"],
            "pro_saas": ["basic_scan", "manual_cleanup", "sha256_duplicates", "dev_cleaner", "treemap_visual", "json_export", "purge_backups"],
            "enterprise": ["basic_scan", "manual_cleanup", "sha256_duplicates", "dev_cleaner", "treemap_visual", "json_export", "purge_backups", "immutable_audit_logs", "multi_tenant", "custom_llm_provider", "air_gapped_nocloud"]
        }
        
        allowed = feature_matrix.get(tier, feature_matrix["pro_saas"])
        if required_feature not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Acceso restringido: La función '{required_feature}' requiere una licencia comercial de nivel Pro SaaS o Enterprise B2B. Plan activo actual: {tier.upper()}."
            )
    finally:
        conn.close()


@router.post("/scan-duplicates", response_model=dict)
async def scan_duplicates(request: DuplicateScanRequest, authorization: Optional[str] = Header(None)):
    """Scan directory for duplicate files by SHA-256."""
    check_license_permission("sha256_duplicates", authorization)
    if not os.path.exists(request.target_path):
        raise HTTPException(status_code=404, detail="Target path not found")
        
    try:
        finder = DuplicateFinder(min_file_size_bytes=request.min_size_mb * 1024 * 1024)
        results = finder.scan_directory_for_duplicates(request.target_path)
        return {
            "ok": True,
            "target_path": request.target_path,
            "total_wasted_bytes": results["total_wasted_bytes"],
            "total_duplicate_files": results["total_duplicate_files"],
            "duplicate_sets": results["duplicate_sets"]
        }
    except Exception as e:
        logger.error(f"Error scanning duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan-dev-artifacts", response_model=dict)
async def scan_dev_artifacts(request: DuplicateScanRequest, authorization: Optional[str] = Header(None)):
    """Scan directory for developer & multimedia artifacts (node_modules, .venv, .next, etc.)."""
    check_license_permission("dev_cleaner", authorization)
    if not os.path.exists(request.target_path):
        raise HTTPException(status_code=404, detail="Target path not found")
        
    try:
        cleaner = DevMediaCleaner()
        results = cleaner.scan_dev_artifacts(request.target_path)
        return {
            "ok": True,
            "target_path": request.target_path,
            "total_artifacts": results["total_artifacts"],
            "total_size_bytes": results["total_size_bytes"],
            "formatted_size": DiskCleaner._format_size(results["total_size_bytes"]),
            "artifacts": results["artifacts"]
        }
    except Exception as e:
        logger.error(f"Error scanning dev artifacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-logs", response_model=dict)
async def get_audit_logs(limit: int = 30, authorization: Optional[str] = Header(None)):
    """Get immutable B2B audit logs of all cleanup operations for current organization."""
    check_license_permission("immutable_audit_logs", authorization)
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT l.id, l.org_id, o.name as org_name, l.host_id, h.hostname,
                   l.categories, l.files_deleted_count, l.bytes_freed,
                   l.backup_path, l.ai_provider, l.ai_analysis_summary, l.executed_at
            FROM cleanup_audit_logs l
            LEFT JOIN organizations o ON l.org_id = o.id
            LEFT JOIN hosts h ON l.host_id = h.id
            WHERE l.org_id = %s
            ORDER BY l.executed_at DESC
            LIMIT %s
        """, (org_id, limit))
        rows = cursor.fetchall()
        
        logs = []
        for r in rows:
            logs.append({
                "id": r[0],
                "org_id": r[1],
                "organization_name": r[2] or "Organización Principal",
                "host_id": r[3],
                "hostname": r[4] or "localhost",
                "categories": r[5],
                "files_deleted_count": r[6],
                "bytes_freed": r[7],
                "formatted_bytes_freed": DiskCleaner._format_size(r[7] or 0),
                "backup_path": r[8],
                "ai_provider": r[9] or "MiniMax AI",
                "ai_analysis_summary": r[10] or "Limpieza segura ejecutada.",
                "executed_at": r[11].isoformat() if r[11] else None
            })
            
        return {"ok": True, "logs": logs}
    finally:
        conn.close()


@router.get("/backup-purge-notifications", response_model=dict)
async def check_backup_purge_notifications():
    """Check for backup directories older than 25 days pending 30-day auto-purge."""
    backup_root = os.path.join(os.path.expanduser("~"), ".ai-infra-monitor", "cleanup_backup")
    if not os.path.exists(backup_root):
        return {"ok": True, "pending_purges": []}
        
    pending = []
    now = datetime.now().timestamp()
    warn_threshold = 25 * 24 * 60 * 60 # 25 days
    
    try:
        for item in os.listdir(backup_root):
            item_path = os.path.join(backup_root, item)
            if os.path.isdir(item_path):
                mtime = os.path.getmtime(item_path)
                age_seconds = now - mtime
                age_days = int(age_seconds // (24 * 3600))
                
                if age_seconds >= warn_threshold:
                    days_remaining = max(0, 30 - age_days)
                    pending.append({
                        "backup_folder": item,
                        "backup_path": item_path,
                        "age_days": age_days,
                        "days_remaining": days_remaining,
                        "auto_purge_scheduled": True
                    })
                    
        return {"ok": True, "pending_purges": pending}
    except Exception as e:
        logger.error(f"Error checking backup purge notifications: {e}")
        return {"ok": False, "error": str(e), "pending_purges": []}


@router.get("/license-info", response_model=dict)
async def get_license_info(authorization: Optional[str] = Header(None)):
    """Get active organization license tier, B2B feature flags, and active LLM provider."""
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, license_tier, created_at FROM organizations WHERE id = %s;", (org_id,))
        row = cursor.fetchone()
        
        org_id = row[0] if row else org_id
        org_name = row[1] if row else "Organización Principal"
        license_tier = row[2] if row else "pro_saas"
        
        adapter = LLMAdapter()
        active_provider = adapter.provider.get_provider_name()
        
        features = {
            "starter": ["basic_scan", "manual_cleanup"],
            "pro_saas": ["basic_scan", "manual_cleanup", "sha256_duplicates", "dev_cleaner", "treemap_visual", "json_export", "purge_backups"],
            "enterprise": ["basic_scan", "manual_cleanup", "sha256_duplicates", "dev_cleaner", "treemap_visual", "json_export", "purge_backups", "immutable_audit_logs", "multi_tenant", "custom_llm_provider", "air_gapped_nocloud"]
        }
        
        allowed = features.get(license_tier, features["pro_saas"])
        
        return {
            "ok": True,
            "organization_id": org_id,
            "organization_name": org_name,
            "license_tier": license_tier.upper(),
            "active_llm_provider": active_provider,
            "allowed_features": allowed,
            "max_hosts": 100 if license_tier == "enterprise" else 10,
            "status": "ACTIVE"
        }
    finally:
        conn.close()


@router.post("/activate-license", response_model=dict)
async def activate_license(request: ActivateLicenseRequest, authorization: Optional[str] = Header(None)):
    """Validate and activate a B2B license key string for current organization."""
    org_id = get_current_org_id(authorization)
    key = request.license_key.upper().strip()
    
    tier = "pro_saas"
    if "ENT" in key or "ENTERPRISE" in key:
        tier = "enterprise"
    elif "STARTER" in key or "FREE" in key:
        tier = "starter"
        
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE organizations SET license_tier = %s WHERE id = %s;", (tier, org_id))
        conn.commit()
        
        return {
            "ok": True,
            "message": f"¡Licencia {tier.upper()} activada con éxito para la Organización!",
            "license_tier": tier.upper()
        }
    finally:
        conn.close()


@router.get("/treemap/{scan_id}", response_model=dict)
async def get_treemap(scan_id: int):
    """Get hierarchical Treemap data structure for scan visualization."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT categories FROM disk_scans WHERE id = %s", (scan_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scan not found")
            
        categories = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        
        children = []
        for cat_name, cat_data in categories.items():
            if cat_name not in ['disk_info', 'drive'] and isinstance(cat_data, dict):
                children.append({
                    "name": cat_data.get("display_name", cat_name),
                    "category_key": cat_name,
                    "value": cat_data.get("total_size", 0),
                    "file_count": cat_data.get("file_count", 0),
                    "risk_level": cat_data.get("risk_level", "low")
                })
                
        return {
            "name": f"Scan #{scan_id}",
            "children": children
        }
    finally:
        conn.close()


@router.post("/export-report", response_model=dict)
async def export_report(request: ExportReportRequest):
    """Export diagnostic report in JSON format (and PDF metadata)."""
    check_license_permission("json_export")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, host_id, total_size_bytes, categories, started_at FROM disk_scans WHERE id = %s", (request.scan_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scan not found")
            
        scan_id, host_id, total_size, categories, started_at = row
        cats = categories if isinstance(categories, dict) else json.loads(categories)
        
        adapter = LLMAdapter()
        ai_report = await adapter.analyze_disk_scan({"total_files": 0, "total_size_bytes": total_size, "categories": cats})
        
        export_payload = {
            "report_title": f"Informe Corporativo de Diagnóstico de Disco (Scan #{scan_id})",
            "scan_id": scan_id,
            "host_id": host_id,
            "generated_at": datetime.now().isoformat(),
            "export_format": request.format.upper(),
            "total_size_bytes": total_size,
            "ai_diagnosis": ai_report,
            "categories_breakdown": cats
        }
        
        return {
            "ok": True,
            "format": request.format,
            "report_data": export_payload
        }
    finally:
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
async def list_scans(host_id: int = None, limit: int = 10, authorization: Optional[str] = Header(None)):
    """
    List all scans filtered by current organization.
    """
    org_id = get_current_org_id(authorization)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if host_id:
            cursor.execute(
                """
                SELECT id, host_id, status, total_size_bytes, started_at, completed_at
                FROM disk_scans
                WHERE org_id = %s AND host_id = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (org_id, host_id, limit)
            )
        else:
            cursor.execute(
                """
                SELECT id, host_id, status, total_size_bytes, started_at, completed_at
                FROM disk_scans
                WHERE org_id = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (org_id, limit)
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
async def perform_cleanup(request: CleanupRequest, authorization: Optional[str] = Header(None)):
    """
    Perform cleanup for selected categories.
    """
    org_id = get_current_org_id(authorization)
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
            (scan_id, host_id, org_id, status, categories_cleaned, started_at)
            VALUES (%s, %s, %s, 'running', %s, NOW())
            RETURNING id
            """,
            (request.scan_id, host_id, org_id, request.categories)
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
        
        # Insert B2B Audit Log
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cleanup_audit_logs 
                (org_id, host_id, categories, files_deleted_count, bytes_freed, backup_path, ai_provider, ai_analysis_summary)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                org_id,
                host_id,
                request.categories,
                cleanup_results['files_deleted'],
                cleanup_results['size_freed'],
                cleanup_results.get('backup_path'),
                "MiniMax AI",
                f"Limpieza de {len(request.categories)} categorías ejecutada con respaldo seguro."
            ))
            conn.commit()
            cursor.close()
        except Exception as audit_err:
            logger.warning(f"Could not record audit log: {audit_err}")
            
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
async def list_cleanups(scan_id: int = None, limit: int = 10, authorization: Optional[str] = Header(None)):
    """
    List cleanup operations filtered by current organization.
    """
    org_id = get_current_org_id(authorization)
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
                WHERE org_id = %s AND scan_id = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (org_id, scan_id, limit)
            )
        else:
            cursor.execute(
                """
                SELECT id, scan_id, host_id, status, categories_cleaned,
                       total_files_deleted, total_size_freed_bytes, backup_path,
                       started_at, completed_at
                FROM cleanup_operations
                WHERE org_id = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (org_id, limit)
            )
        
        rows = cursor.fetchall()
        cursor.close()
        
        operations = []
        for row in rows:
            b_path = row[7]
            b_exists = os.path.exists(b_path) if b_path else False
            operations.append({
                "operation_id": row[0],
                "scan_id": row[1],
                "host_id": row[2],
                "status": row[3],
                "categories_cleaned": row[4],
                "files_deleted": row[5],
                "size_freed": row[6],
                "backup_path": b_path,
                "backup_exists": b_exists,
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
