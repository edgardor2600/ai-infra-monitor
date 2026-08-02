"""
Disk Analyzer API Routes

This module provides endpoints for disk analysis and cleanup operations.
"""

import os
import json
import socket
import logging
import psycopg2
from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Header, Response
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime, timezone
from backend.api.routes.auth import decode_jwt_token

from backend.api.models.disk_analyzer import (
    ScanRequest,
    AgentScanPayload,
    AgentTaskResultPayload,
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
    ActivateLicenseRequest,
    CreateScheduledCleanupRequest
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


def extract_metrics_dict_from_payload(payload) -> dict:
    """Extract metric name-value pairs from telemetry payload (list or dict)."""
    if not payload:
        return {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return {}
            
    metrics_dict = {}
    samples = []
    if isinstance(payload, list):
        samples = payload
    elif isinstance(payload, dict):
        if 'samples' in payload and isinstance(payload['samples'], list):
            samples = payload['samples']
        elif 'metrics' in payload:
            if isinstance(payload['metrics'], list):
                samples = payload['metrics']
            elif isinstance(payload['metrics'], dict):
                return payload['metrics']

    if isinstance(samples, list):
        for item in samples:
            if isinstance(item, dict) and 'metric' in item:
                metrics_dict[item['metric']] = item.get('value')

    return metrics_dict


def check_license_permission(feature_name: str, authorization: Optional[str] = None):
    """Verify if active organization license tier has permission for feature_name."""
    org_id = get_current_org_id(authorization)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT license_tier FROM organizations WHERE id = %s;", (org_id,))
        row = cursor.fetchone()
        license_tier = (row[0] if (row and row[0]) else "pro_saas").lower()
        if license_tier in ['pro', 'pro_saas', 'pro_saas_phase1', 'pro_saas_phase2']:
            license_tier = 'pro_saas'

        features = {
            "starter": ["basic_scan", "manual_cleanup"],
            "pro_saas": ["basic_scan", "manual_cleanup", "sha256_duplicates", "dev_cleaner", "treemap_visual", "json_export", "purge_backups", "immutable_audit_logs"],
            "enterprise": ["basic_scan", "manual_cleanup", "sha256_duplicates", "dev_cleaner", "treemap_visual", "json_export", "purge_backups", "immutable_audit_logs", "multi_tenant", "custom_llm_provider", "air_gapped_nocloud"]
        }

        allowed = features.get(license_tier, features["pro_saas"])
        if feature_name not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"La función '{feature_name}' requiere una licencia comercial Pro SaaS o Enterprise B2B."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking license permission: {e}")
    finally:
        if conn:
            conn.close()


from backend.db.connection import get_db_connection


@router.get("/drives", response_model=dict)
async def get_drives(host_id: Optional[int] = None, authorization: Optional[str] = Header(None)):
    """Get list of available disk drives and free space info for host using agent telemetry.
    
    Returns active_host_id so the frontend always knows which host is currently transmitting
    metrics, avoiding the host_id mismatch that causes CPU 0% and 'Agent Disconnected' errors.
    """
    org_id = get_current_org_id(authorization)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Threshold: agente se considera "vivo" si envió métricas hace menos de 10 minutos
        AGENT_LIVE_THRESHOLD_SECONDS = 600

        # Buscar la métrica más reciente para la organización (o host específico)
        # IMPORTANTE: siempre resolvemos el active_host_id del agente más reciente de la org
        # para que el frontend sepa exactamente a qué host apuntar.
        active_host_id = host_id  # valor inicial, puede sobreescribirse abajo

        if host_id:
            cursor.execute(
                """
                SELECT m.payload, m.created_at, m.host_id FROM metrics_raw m
                WHERE m.host_id = %s
                ORDER BY m.created_at DESC LIMIT 10
                """,
                (host_id,)
            )
        else:
            # Sin host_id explícito: buscar el host con métricas MÁS RECIENTES de esta org
            # Esto resuelve el caso de "agente corriendo como host_id=3 pero frontend ve host_id=2"
            cursor.execute(
                """
                SELECT m.payload, m.created_at, m.host_id FROM metrics_raw m
                JOIN hosts h ON m.host_id = h.id
                WHERE h.org_id = %s
                ORDER BY m.created_at DESC LIMIT 10
                """,
                (org_id,)
            )

        rows = cursor.fetchall()

        # Fallback si no hay métricas para la org: consultar cualquier métrica reciente
        if not rows:
            cursor.execute(
                "SELECT payload, created_at, host_id FROM metrics_raw ORDER BY created_at DESC LIMIT 10;"
            )
            rows = cursor.fetchall()

        if rows:
            latest_row = rows[0]
            last_seen_at = latest_row[1]
            # Capturar el host_id real del agente con métricas más recientes
            active_host_id = latest_row[2] if latest_row[2] is not None else host_id

            # Verificar frescura de la telemetría con cálculo seguro de timezone
            now_utc = datetime.now(timezone.utc)
            if hasattr(last_seen_at, 'tzinfo') and last_seen_at.tzinfo is not None:
                ls_utc = last_seen_at.astimezone(timezone.utc)
            else:
                ls_utc = last_seen_at.replace(tzinfo=timezone.utc)

            age_seconds = abs((now_utc - ls_utc).total_seconds())
            is_agent_live = age_seconds < AGENT_LIVE_THRESHOLD_SECONDS
            last_seen_iso = last_seen_at.isoformat()

            logger.info(
                f"[DRIVES] Última telemetría del agente: {last_seen_iso} "
                f"({int(age_seconds)}s atrás) — is_agent_live={is_agent_live} — active_host_id={active_host_id}"
            )

            # Buscar valores de disco en la lista de las últimas métricas
            disk_total_gb = None
            disk_free_gb = None
            disk_percent = None

            for r in rows:
                metrics_dict = extract_metrics_dict_from_payload(r[0])
                if metrics_dict.get('disk_total_gb') and metrics_dict.get('disk_free_gb'):
                    disk_total_gb = metrics_dict.get('disk_total_gb')
                    disk_free_gb = metrics_dict.get('disk_free_gb')
                    disk_percent = metrics_dict.get('disk_percent')
                    break

            if disk_total_gb and disk_free_gb:
                total_bytes = int(float(disk_total_gb) * (1024 ** 3))
                free_bytes = int(float(disk_free_gb) * (1024 ** 3))
                used_bytes = max(0, total_bytes - free_bytes)
                percent = float(disk_percent) if disk_percent is not None else round((used_bytes / max(1, total_bytes)) * 100, 2)
            else:
                # Fallback predeterminado para C: si el agente reporta pero las métricas no incluyen disco aún
                total_bytes = 512 * (1024 ** 3)
                free_bytes = 100 * (1024 ** 3)
                used_bytes = total_bytes - free_bytes
                percent = 80.47

            drives = [{'device': 'C:', 'drive': 'C:', 'mountpoint': 'C:\\', 'fstype': 'NTFS',
                       'total': total_bytes, 'used': used_bytes, 'free': free_bytes,
                       'free_bytes': free_bytes, 'total_bytes': total_bytes, 'used_bytes': used_bytes,
                       'used_percent': percent, 'percent_used': percent}]

            return {
                "drives": drives,
                "is_agent_live": is_agent_live,
                "active_host_id": active_host_id,
                "agent_last_seen_at": last_seen_iso,
                "agent_data_age_seconds": int(age_seconds)
            }

        # No hay registros en metrics_raw
        return {
            "drives": [],
            "is_agent_live": False,
            "active_host_id": None,
            "agent_last_seen_at": None,
            "agent_data_age_seconds": None
        }

    except Exception as e:
        logger.warning(f"[DRIVES] Error fetching host disk metrics from DB: {e}")
    finally:
        if conn:
            conn.close()

    logger.info("[DRIVES] Sin telemetría disponible — agente no activo o nunca conectado")
    return {
        "drives": [],
        "is_agent_live": False,
        "active_host_id": None,
        "agent_last_seen_at": None,
        "agent_data_age_seconds": None
    }


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

        # Check if host is local to run direct disk scanner
        cursor.execute("SELECT hostname FROM hosts WHERE id = %s;", (host_id,))
        hrow = cursor.fetchone()
        local_hostname = socket.gethostname()
        is_local_host = (
            not hrow 
            or hrow[0] == local_hostname 
            or (hrow[0] and hrow[0].lower() in ['localhost', '127.0.0.1', 'local', ''])
            or host_id == 1
        )

        logger.info(f"[SCAN TASK] host_id={host_id}, hostname={hrow[0] if hrow else 'unknown'}, local_hostname={local_hostname}, is_local={is_local_host}")

        scan_results = None
        if is_local_host:
            try:
                logger.info(f"[SCAN TASK] ⚡ Ejecutando DiskScanner local para host_id={host_id}, drive={drive}")
                scanner = DiskScanner(host_id, drive=drive)
                scan_results = scanner.scan_all_categories()
                total_files = sum(c.get('file_count', 0) for c in scan_results.get('categories', {}).values() if isinstance(c, dict))
                logger.info(f"[SCAN TASK] ✅ Scan local completado: {total_files} archivos encontrados, {scan_results.get('total_size_formatted', '?')} en {drive}")
            except Exception as scan_err:
                logger.warning(f"[SCAN TASK] ⚠️ DiskScanner local falló, buscando datos del agente en DB: {scan_err}")

        if not scan_results:
            # ─── VERIFICAR SI EL AGENTE LOCAL ESTÁ ACTIVO (métricas recientes) ───
            AGENT_LIVE_THRESHOLD_SECONDS = 600  # 10 minutos
            cursor.execute(
                "SELECT MAX(created_at) FROM metrics_raw WHERE host_id = %s",
                (host_id,)
            )
            last_metric_row = cursor.fetchone()
            last_metric_at = last_metric_row[0] if last_metric_row else None
            agent_is_live = False
            if last_metric_at:
                last_metric_naive = last_metric_at.replace(tzinfo=None) if hasattr(last_metric_at, 'tzinfo') and last_metric_at.tzinfo else last_metric_at
                age_s = (datetime.utcnow() - last_metric_naive).total_seconds()
                agent_is_live = age_s < AGENT_LIVE_THRESHOLD_SECONDS
                logger.info(f"[SCAN TASK] Agente - última telemetría hace {int(age_s)}s — is_alive={agent_is_live}")

            if agent_is_live:
                # ─── AGENTE VIVO: Encolar tarea de escaneo para ejecutarse localmente ───
                # El agente correrá scan_local_cleanup_paths() en la máquina real del usuario
                # y enviará resultados reales via /agent-scan-results
                logger.info(f"[SCAN TASK] ⚡ Agente activo — creando tarea 'run_disk_scan' para que el agente escanee el disco real...")
                task_payload = {
                    "scan_id": scan_id,
                    "drive": drive
                }
                cursor.execute(
                    """
                    INSERT INTO cleanup_tasks (host_id, org_id, scan_id, task_type, payload, status)
                    VALUES (%s, (SELECT org_id FROM disk_scans WHERE id = %s LIMIT 1), %s, 'run_disk_scan', %s, 'pending')
                    RETURNING id
                    """,
                    (host_id, scan_id, scan_id, json.dumps(task_payload))
                )
                task_id = cursor.fetchone()[0]
                conn.commit()
                logger.info(f"[SCAN TASK] ✅ Tarea de escaneo #{task_id} encolada para agente (host_id={host_id}) — el scan_id={scan_id} se actualizará cuando el agente complete")
                # El scan queda en 'running' hasta que el agente envíe resultados via /agent-scan-results
                cursor.close()
                return

            # ─── AGENTE OFFLINE: Usar fallback con datos existentes en DB ───
            logger.info(f"[SCAN TASK] 🔍 Agente offline — buscando escaneo previo en DB para host_id={host_id}...")
            cursor.execute(
                """
                SELECT categories, total_size_bytes FROM disk_scans
                WHERE host_id = %s AND status = 'completed' AND categories IS NOT NULL AND id != %s
                ORDER BY completed_at DESC LIMIT 1
                """,
                (host_id, scan_id)
            )
            agent_scan_row = cursor.fetchone()
            if agent_scan_row and agent_scan_row[0]:
                agent_categories = agent_scan_row[0]
                if isinstance(agent_categories, str):
                    agent_categories = json.loads(agent_categories)
                agent_total_size = agent_scan_row[1] or 0
                
                categories_with_disk_info = agent_categories.copy()
                categories_with_disk_info['drive'] = drive

                if 'disk_info' not in categories_with_disk_info or not isinstance(categories_with_disk_info.get('disk_info'), dict) or not categories_with_disk_info['disk_info'].get('total'):
                    cursor.execute(
                        "SELECT payload FROM metrics_raw WHERE host_id = %s ORDER BY created_at DESC LIMIT 1",
                        (host_id,)
                    )
                    mrow = cursor.fetchone()
                    if mrow and mrow[0]:
                        m_dict = extract_metrics_dict_from_payload(mrow[0])
                        dt_gb = m_dict.get('disk_total_gb')
                        df_gb = m_dict.get('disk_free_gb')
                        dp = m_dict.get('disk_percent')
                        if dt_gb and df_gb:
                            tot = int(float(dt_gb) * (1024 ** 3))
                            fre = int(float(df_gb) * (1024 ** 3))
                            usd = tot - fre
                            pct = float(dp) if dp is not None else round((usd / tot) * 100, 2)
                            categories_with_disk_info['disk_info'] = {
                                "drive": drive,
                                "device": drive,
                                "total": tot,
                                "used": usd,
                                "free": fre,
                                "used_percent": pct,
                                "percent_used": pct
                            }
                
                cursor.execute(
                    """
                    UPDATE disk_scans 
                    SET status = 'completed',
                        total_size_bytes = %s,
                        categories = %s,
                        completed_at = NOW()
                    WHERE id = %s
                    """,
                    (agent_total_size, json.dumps(categories_with_disk_info), scan_id)
                )
                conn.commit()

                for cat_name, cat_data in agent_categories.items():
                    if isinstance(cat_data, dict):
                        for file_info in cat_data.get('files', []):
                            cursor.execute(
                                """
                                INSERT INTO cleanup_items 
                                (scan_id, category, file_path, file_size_bytes, last_accessed, is_safe, risk_level)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    scan_id,
                                    cat_name,
                                    file_info.get('path', 'unknown'),
                                    file_info.get('size', 0),
                                    file_info.get('last_accessed'),
                                    file_info.get('is_safe', True),
                                    file_info.get('risk_level', 'low')
                                )
                            )
                conn.commit()
                cursor.close()
                logger.info(f"[SCAN TASK] ✅ Scan completado usando telemetría del agente (fallback) para host_id={host_id}, scan_id={scan_id}")
                return
            else:
                logger.warning(f"[SCAN TASK] ⚠️ Host {host_id} sin telemetría disponible y sin datos del agente — scan marcado como failed")
                logger.info(f"[SCAN TASK] Host ID {host_id} es remoto y no tiene telemetría disponible.")
                cursor.execute(
                    """
                    UPDATE disk_scans 
                    SET status = 'failed',
                        error_message = %s,
                        completed_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        "Esperando datos del agente remoto. Por favor ejecuta 'python agent/standalone_agent.py' en el equipo destino.",
                        scan_id
                    )
                )
                conn.commit()
                cursor.close()
                return

        
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


@router.post("/agent-scan-results", response_model=dict)
async def receive_agent_scan_results(payload: AgentScanPayload):
    """Receive real local disk scan results directly from a running agent."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT org_id FROM hosts WHERE id = %s;", (payload.host_id,))
        hrow = cursor.fetchone()
        org_id = hrow[0] if hrow else payload.org_id

        categories_with_disk_info = payload.categories.copy()
        categories_with_disk_info['drive'] = payload.drive
        if payload.disk_info:
            categories_with_disk_info['disk_info'] = payload.disk_info

        if payload.existing_scan_id:
            # ─── ACTUALIZAR scan existente (flujo 'run_disk_scan' task) ───
            # El agente completa el scan que el backend había dejado en 'running'
            logger.info(f"[AGENT-SCAN] Actualizando scan existente id={payload.existing_scan_id} con resultados reales del agente")
            cursor.execute(
                """
                UPDATE disk_scans
                SET status = 'completed',
                    total_size_bytes = %s,
                    categories = %s,
                    completed_at = NOW()
                WHERE id = %s
                """,
                (payload.total_size_bytes, json.dumps(categories_with_disk_info), payload.existing_scan_id)
            )
            conn.commit()
            scan_id = payload.existing_scan_id

            # Limpiar cleanup_items del scan anterior e insertar los nuevos
            cursor.execute("DELETE FROM cleanup_items WHERE scan_id = %s", (scan_id,))
            conn.commit()
        else:
            # ─── INSERTAR nuevo scan (flujo inicial del agente al arrancar) ───
            cursor.execute(
                """
                INSERT INTO disk_scans (host_id, org_id, status, total_size_bytes, categories, started_at, completed_at)
                VALUES (%s, %s, 'completed', %s, %s, NOW(), NOW())
                RETURNING id
                """,
                (payload.host_id, org_id, payload.total_size_bytes, json.dumps(categories_with_disk_info))
            )
            scan_id = cursor.fetchone()[0]
            conn.commit()

        total_files = 0
        for cat_name, cat_data in payload.categories.items():
            if isinstance(cat_data, dict):
                for file_info in cat_data.get('files', []):
                    cursor.execute(
                        """
                        INSERT INTO cleanup_items 
                        (scan_id, category, file_path, file_size_bytes, last_accessed, is_safe, risk_level)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            scan_id,
                            cat_name,
                            file_info.get('path', 'unknown'),
                            file_info.get('size', 0),
                            file_info.get('last_accessed'),
                            file_info.get('is_safe', True),
                            file_info.get('risk_level', 'low')
                        )
                    )
                    total_files += 1
        conn.commit()
        cursor.close()
        logger.info(f"[AGENT-SCAN] ✅ Scan id={scan_id} guardado con {total_files} rutas reales de archivos")
        return {"ok": True, "scan_id": scan_id}
    except Exception as e:
        logger.error(f"Error saving agent scan results: {e}")
        raise HTTPException(status_code=500, detail=str(e))
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
        
        disk_info = categories_data.get("disk_info", {})
        if not disk_info or not disk_info.get("total"):
            try:
                import shutil
                drive_letter = categories_data.get("drive", "C:")
                drive_root = drive_letter.rstrip("\\").rstrip("/") + "\\"
                dt, du, df = shutil.disk_usage(drive_root)
                percent = round((du / dt) * 100, 2)
                disk_info = {
                    "drive": drive_letter,
                    "total": dt,
                    "used": du,
                    "free": df,
                    "used_percent": percent,
                    "percent_used": percent
                }
            except Exception:
                disk_info = {"used_percent": 0.0, "percent_used": 0.0}

        scan_summary = {
            "scan_id": request.scan_id,
            "total_size_bytes": total_size,
            "total_size_formatted": DiskCleaner._format_size(total_size),
            "total_files": total_files,
            "disk_info": disk_info,
            "categories": categories_data
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
async def purge_backup(request: PurgeBackupRequest, authorization: Optional[str] = Header(None)):
    """Purge a backup folder to immediately free disk space."""
    org_id = get_current_org_id(authorization)
    
    if os.path.exists(request.backup_path):
        res = DiskCleaner.purge_backup_path(request.backup_path)
        if not res.get('success'):
            raise HTTPException(status_code=400, detail=res.get('message'))
        return res

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        host_id = 1
        if request.scan_id:
            cursor.execute("SELECT host_id FROM disk_scans WHERE id = %s AND org_id = %s", (request.scan_id, org_id))
            hrow = cursor.fetchone()
            if hrow:
                host_id = hrow[0]
        else:
            cursor.execute("SELECT id FROM hosts WHERE org_id = %s ORDER BY created_at DESC LIMIT 1", (org_id,))
            hrow = cursor.fetchone()
            if hrow:
                host_id = hrow[0]

        payload = {"backup_path": request.backup_path, "scan_id": request.scan_id}
        cursor.execute(
            """
            INSERT INTO cleanup_tasks (host_id, org_id, scan_id, task_type, payload, status)
            VALUES (%s, %s, %s, 'purge_backup', %s, 'pending')
            RETURNING id
            """,
            (host_id, org_id, request.scan_id, json.dumps(payload))
        )
        task_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        
        return {
            "ok": True,
            "success": True,
            "task_id": task_id,
            "status": "pending",
            "message": "Solicitud de liberación de resguardo enviada al agente del equipo."
        }
    finally:
        conn.close()


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
        
        formatted_sets = []
        for dset in results.get("duplicate_sets", []):
            all_paths = [dset["original_path"]] + dset.get("duplicate_paths", [])
            files_list = [{"path": p, "is_original": (i == 0)} for i, p in enumerate(all_paths)]
            formatted_sets.append({
                "sha256": dset["sha256"],
                "sha256_hash": dset["sha256"],
                "original_path": dset["original_path"],
                "duplicate_paths": dset.get("duplicate_paths", []),
                "files": files_list,
                "file_size_bytes": dset["file_size_bytes"],
                "wasted_bytes": dset["wasted_bytes"],
                "file_count": dset.get("file_count", len(all_paths))
            })
            
        return {
            "ok": True,
            "target_path": request.target_path,
            "total_wasted_bytes": results["total_wasted_bytes"],
            "total_duplicate_files": results["total_duplicate_files"],
            "duplicate_sets": formatted_sets
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
        license_tier = (row[2] if (row and row[2]) else "pro_saas").lower()
        if license_tier in ['pro', 'pro_saas', 'pro_saas_phase1', 'pro_saas_phase2']:
            license_tier = 'pro_saas'
        
        adapter = LLMAdapter()
        active_provider = adapter.provider.get_provider_name()
        
        features = {
            "starter": ["basic_scan", "manual_cleanup"],
            "pro_saas": ["basic_scan", "manual_cleanup", "sha256_duplicates", "dev_cleaner", "treemap_visual", "json_export", "purge_backups", "immutable_audit_logs"],
            "pro": ["basic_scan", "manual_cleanup", "sha256_duplicates", "dev_cleaner", "treemap_visual", "json_export", "purge_backups", "immutable_audit_logs"],
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


@router.post("/export-pdf")
async def export_pdf_report(request: ExportReportRequest, authorization: Optional[str] = Header(None)):
    """Export executive diagnostic report in PDF format."""
    from fastapi.responses import Response
    from backend.disk_analyzer.pdf_exporter import generate_executive_pdf_report

    check_license_permission("json_export", authorization)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, host_id, total_size_bytes, categories FROM disk_scans WHERE id = %s", (request.scan_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scan not found")
            
        scan_id, host_id, total_size, categories = row
        cats = categories if isinstance(categories, dict) else json.loads(categories)
        
        adapter = LLMAdapter()
        ai_report = await adapter.analyze_disk_scan({"total_files": 0, "total_size_bytes": total_size, "categories": cats})
        
        pdf_bytes = generate_executive_pdf_report(scan_id=scan_id, scan_data={"total_size_bytes": total_size, "categories": cats}, ai_report=ai_report)
        
        media_type = "application/pdf" if pdf_bytes.startswith(b"%PDF") else "text/html"
        filename = f"Informe_Corporativo_Scan_{scan_id}.pdf" if media_type == "application/pdf" else f"Informe_Corporativo_Scan_{scan_id}.html"
        
        return Response(
            content=pdf_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    finally:
        conn.close()


@router.get("/scan/{scan_id}", response_model=dict)
async def get_scan(scan_id: int, authorization: Optional[str] = Header(None)):
    """
    Get scan results by ID (isolated by organization).
    """
    org_id = get_current_org_id(authorization)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT id, host_id, status, total_size_bytes, categories, 
                   recommendations, error_message, started_at, completed_at
            FROM disk_scans
            WHERE id = %s AND org_id = %s
            """,
            (scan_id, org_id)
        )
        
        row = cursor.fetchone()
        cursor.close()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scan {scan_id} not found"
            )
        
        categories_data = row[4] if row[4] else {}
        
        # Extract disk_info if it exists in categories or generate telemetry fallback
        disk_info = categories_data.get('disk_info', None) if isinstance(categories_data, dict) else None
        if not disk_info:
            host_id = row[1]
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT payload FROM metrics_raw WHERE host_id = %s ORDER BY created_at DESC LIMIT 1",
                    (host_id,)
                )
                mrow = cursor.fetchone()
                if mrow and mrow[0]:
                    payload = mrow[0]
                    metrics_dict = extract_metrics_dict_from_payload(payload)

                    dt_gb = metrics_dict.get('disk_total_gb')
                    df_gb = metrics_dict.get('disk_free_gb')
                    dp = metrics_dict.get('disk_percent')
                    if dt_gb and df_gb:
                        tot = int(float(dt_gb) * (1024 ** 3))
                        fre = int(float(df_gb) * (1024 ** 3))
                        usd = tot - fre
                        pct = float(dp) if dp is not None else round((usd / tot) * 100, 2)
                        disk_info = {
                            "drive": "C:",
                            "device": "C:",
                            "total": tot,
                            "used": usd,
                            "free": fre,
                            "used_percent": pct,
                            "percent_used": pct
                        }
            except Exception as e:
                logger.warning(f"Error fetching telemetry for scan host_id {host_id}: {e}")

            if disk_info and not disk_info.get("total"):
                disk_info = None

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
    List all scans filtered by current organization (or system default org 1).
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
    logger.info(f"[CLEANUP] 🧹 Iniciando cleanup — scan_id={request.scan_id}, org_id={org_id}, categorias={request.categories}, create_backup={request.create_backup}")
    
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
        
        cursor.execute("SELECT hostname FROM hosts WHERE id = %s;", (host_id,))
        hrow = cursor.fetchone()
        local_hostname = socket.gethostname()
        is_local = (hrow and hrow[0] == local_hostname)

        logger.info(f"[CLEANUP] Host info — host_id={host_id}, hostname={hrow[0] if hrow else 'unknown'}, local_hostname={local_hostname}, is_local={is_local}")
        logger.info(f"[CLEANUP] Archivos por categoría:")
        for cat_name, files in files_by_category.items():
            logger.info(f"[CLEANUP]   {cat_name}: {len(files)} archivos")

        if is_local:
            cleaner = DiskCleaner(host_id, request.scan_id)
            cleanup_results = cleaner.cleanup_categories(
                request.categories,
                files_by_category,
                request.create_backup
            )
            
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
        else:
            task_payload = {
                "operation_id": operation_id,
                "categories": request.categories,
                "create_backup": request.create_backup,
                "files_by_category": files_by_category
            }
            cursor.execute(
                """
                INSERT INTO cleanup_tasks (host_id, org_id, scan_id, task_type, payload, status)
                VALUES (%s, %s, %s, 'cleanup_categories', %s, 'pending')
                RETURNING id
                """,
                (host_id, org_id, request.scan_id, json.dumps(task_payload))
            )
            task_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            logger.info(f"[CLEANUP] ⏳ Tarea encolada para agente remoto — task_id={task_id}, operation_id={operation_id}, host_id={host_id}")
            logger.info(f"[CLEANUP] ⚠️ IMPORTANTE: Los archivos NO serán eliminados hasta que el agente local recoja esta tarea")
            
            return {
                "operation_id": operation_id,
                "scan_id": request.scan_id,
                "task_id": task_id,
                "status": "pending",
                "files_deleted": 0,
                "size_freed": 0,
                "backup_path": None,
                "errors": [],
                "message": "Solicitud de limpieza encolada para ejecución remota en el agente del equipo.",
                "started_at": datetime.now().isoformat(),
                "completed_at": None
            }
        
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


@router.post("/scheduled-cleanups", response_model=dict)
async def create_or_update_scheduled_cleanup(
    request: CreateScheduledCleanupRequest,
    authorization: Optional[str] = Header(None)
):
    """Create or update an automated scheduled maintenance job for a host."""
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        
        # Zero-risk enforcement
        safe_cats = [c for c in request.categories if c in {'temp_files', 'browser_cache', 'recycle_bin', 'thumbnails', 'windows_update', 'pkg_managers', 'installers'}]
        if not safe_cats:
            safe_cats = ['temp_files', 'browser_cache', 'recycle_bin']
            
        cursor.execute("""
            INSERT INTO scheduled_disk_cleanups (host_id, org_id, enabled, categories, interval_hours)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE 
            SET enabled = EXCLUDED.enabled,
                categories = EXCLUDED.categories,
                interval_hours = EXCLUDED.interval_hours
            RETURNING id, enabled, categories, interval_hours;
        """, (request.host_id, org_id, request.enabled, safe_cats, request.interval_hours))
        
        row = cursor.fetchone()
        conn.commit()
        
        return {
            "ok": True,
            "schedule_id": row[0],
            "enabled": row[1],
            "categories": row[2],
            "interval_hours": row[3],
            "message": f"Programación de mantenimiento activo cada {row[3]} horas."
        }
    finally:
        conn.close()


@router.get("/scheduled-cleanups", response_model=dict)
async def list_scheduled_cleanups(authorization: Optional[str] = Header(None)):
    """List all scheduled maintenance jobs for current organization."""
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, host_id, enabled, categories, interval_hours, last_run_at, next_run_at, created_at
            FROM scheduled_disk_cleanups
            WHERE org_id = %s
            ORDER BY created_at DESC
        """, (org_id,))
        
        rows = cursor.fetchall()
        schedules = []
        for r in rows:
            schedules.append({
                "id": r[0],
                "host_id": r[1],
                "enabled": r[2],
                "categories": r[3],
                "interval_hours": r[4],
                "last_run_at": r[5].isoformat() if r[5] else None,
                "next_run_at": r[6].isoformat() if r[6] else None,
                "created_at": r[7].isoformat() if r[7] else None
            })
            
        return {
            "ok": True,
            "schedules": schedules,
            "total": len(schedules)
        }
    finally:
        conn.close()


@router.delete("/scheduled-cleanups/{schedule_id}", response_model=dict)
async def delete_scheduled_cleanup(schedule_id: int, authorization: Optional[str] = Header(None)):
    """Delete a scheduled maintenance job by ID."""
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM scheduled_disk_cleanups
            WHERE id = %s AND org_id = %s
        """, (schedule_id, org_id))
        
        conn.commit()
        return {"ok": True, "schedule_id": schedule_id, "message": "Programación eliminada con éxito."}
    finally:
        conn.close()


@router.get("/pending-tasks", response_model=dict)
async def get_pending_tasks(
    host_id: Optional[int] = 1,
    org_id: Optional[int] = None,
    authorization: Optional[str] = Header(None)
):
    """Agent polling endpoint: Retrieve pending cleanup / purge tasks for host or org."""
    target_org_id = org_id or get_current_org_id(authorization)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, task_type, payload, scan_id
            FROM cleanup_tasks
            WHERE (host_id = %s OR org_id = %s) AND status = 'pending'
            ORDER BY created_at ASC
            """,
            (host_id, target_org_id)
        )
        rows = cursor.fetchall()
        tasks = []
        for r in rows:
            p = r[2]
            if isinstance(p, str):
                try:
                    p = json.loads(p)
                except Exception:
                    p = {}
            tasks.append({
                "task_id": r[0],
                "task_type": r[1],
                "payload": p,
                "scan_id": r[3]
            })
            
        for t in tasks:
            cursor.execute("UPDATE cleanup_tasks SET status = 'in_progress' WHERE id = %s", (t["task_id"],))
        conn.commit()
        
        if tasks:
            logger.info(f"⚡ [PENDING-TASKS] Entregadas {len(tasks)} tareas pendientes al agente (Host ID={host_id}, Org ID={target_org_id})")
        return {"ok": True, "tasks": tasks}
    finally:
        conn.close()


@router.post("/task-result", response_model=dict)
async def receive_task_result(payload: AgentTaskResultPayload):
    """Agent reporting endpoint: Receive execution results for a cleanup or purge task."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT host_id, org_id, scan_id, task_type FROM cleanup_tasks WHERE id = %s", (payload.task_id,))
        trow = cursor.fetchone()
        if not trow:
            raise HTTPException(status_code=404, detail="Task not found")
            
        host_id, org_id, scan_id, task_type = trow[0], trow[1], trow[2], trow[3]
        
        cursor.execute(
            """
            UPDATE cleanup_tasks
            SET status = %s,
                result = %s,
                completed_at = NOW()
            WHERE id = %s
            """,
            (payload.status, json.dumps(payload.result), payload.task_id)
        )
        
        files_deleted = payload.result.get('files_deleted', 0)
        size_freed = payload.result.get('size_freed', 0)
        backup_path = payload.result.get('backup_path')
        operation_id = payload.result.get('operation_id')

        if operation_id:
            status_op = 'completed' if payload.status in ['completed', 'completed_with_warnings'] else 'failed'
            err_msg = "\n".join(payload.result.get('errors', [])) if payload.result.get('errors') else None
            cursor.execute(
                """
                UPDATE cleanup_operations
                SET status = %s,
                    total_files_deleted = %s,
                    total_size_freed_bytes = %s,
                    backup_path = %s,
                    error_message = %s,
                    completed_at = NOW()
                WHERE id = %s
                """,
                (
                    status_op,
                    files_deleted,
                    size_freed,
                    backup_path,
                    err_msg,
                    operation_id
                )
            )
        
        if files_deleted > 0 or size_freed > 0 or backup_path:
            try:
                cursor.execute(
                    """
                    INSERT INTO cleanup_audit_logs 
                    (org_id, host_id, categories, files_deleted_count, bytes_freed, backup_path, ai_provider, ai_analysis_summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        org_id,
                        host_id,
                        payload.result.get('categories', ['remote_cleanup']),
                        files_deleted,
                        size_freed,
                        backup_path,
                        "MiniMax AI",
                        f"Ejecución remota exitosa en agente (Host {host_id}): {files_deleted} archivos eliminados, {DiskCleaner._format_size(size_freed)} liberados."
                    )
                )
            except Exception as audit_err:
                logger.warning(f"Error creating audit log for task {payload.task_id}: {audit_err}")

        if payload.disk_info and scan_id:
            cursor.execute("SELECT categories FROM disk_scans WHERE id = %s", (scan_id,))
            srow = cursor.fetchone()
            if srow and srow[0]:
                categories = srow[0]
                if isinstance(categories, str):
                    try:
                        categories = json.loads(categories)
                    except Exception:
                        categories = {}
                categories['disk_info'] = payload.disk_info
                cursor.execute(
                    "UPDATE disk_scans SET categories = %s WHERE id = %s",
                    (json.dumps(categories), scan_id)
                )

        conn.commit()
        return {"ok": True, "task_id": payload.task_id, "status": payload.status}
    finally:
        conn.close()


@router.get("/task-status/{task_id}", response_model=dict)
async def get_task_status(task_id: int, authorization: Optional[str] = Header(None)):
    """Dashboard polling endpoint: Check task execution status."""
    org_id = get_current_org_id(authorization)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, status, result, completed_at
            FROM cleanup_tasks
            WHERE id = %s AND org_id = %s
            """,
            (task_id, org_id)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
            
        result_data = row[2]
        if isinstance(result_data, str):
            try:
                result_data = json.loads(result_data)
            except Exception:
                result_data = {}
                
        return {
            "ok": True,
            "task_id": row[0],
            "status": row[1],
            "result": result_data or {},
            "completed_at": row[3].isoformat() if row[3] else None
        }
    finally:
        conn.close()


@router.get("/download-launcher")
async def download_launcher(os_type: str = "windows", authorization: Optional[str] = Header(None)):
    """Generate and serve a customized 1-click launcher script (.bat or .sh) tailored for user's organization.
    
    CRITICAL: The generated script embeds AGENT_TOKEN (the user's JWT) and AGENT_ORG_ID so that
    the agent authenticates with the backend using the same identity as the logged-in user.
    This prevents the org_id mismatch that causes 'Agent Disconnected' and CPU 0% errors.
    """
    org_id = get_current_org_id(authorization)
    backend_url = os.getenv("BACKEND_URL", "https://ai-infra-monitor-api.onrender.com").rstrip("/")

    # Extract the raw JWT token to embed it in the launcher script.
    # The agent will use this token to authenticate with the backend, ensuring it registers
    # under the correct org_id instead of falling back to org_id=1.
    agent_token = ""
    if authorization and authorization.startswith("Bearer "):
        agent_token = authorization.split(" ", 1)[1].strip()

    if os_type.lower() in ["linux", "macos", "bash"]:
        content = f"""#!/bin/bash
# ============================================================
#  AI Infra Monitor — Agente de Monitoreo Local
#  Organizacion ID: {org_id}
#  Generado automaticamente para tu cuenta. No compartas este archivo.
# ============================================================
echo "========================================================"
echo " Iniciando Servidor de Monitoreo Local"
echo " Organizacion ID: {org_id}"
echo "========================================================"
export BACKEND_URL="{backend_url}"
export AGENT_ORG_ID="{org_id}"
export AGENT_TOKEN="{agent_token}"

curl -s "{backend_url}/agent/standalone_agent.py" -o standalone_agent.py 2>/dev/null || \
    wget -q "{backend_url}/agent/standalone_agent.py" -O standalone_agent.py 2>/dev/null

if [ ! -f standalone_agent.py ]; then
    echo "[ERROR] No se pudo descargar standalone_agent.py. Verifica tu conexion a internet."
    exit 1
fi

echo " Ejecutando servidor de monitoreo en vivo (Org ID: {org_id})..."
python3 standalone_agent.py
"""
        filename = f"iniciar_servidor_org_{org_id}.sh"
        media_type = "application/x-sh"
    else:
        content = f"""@echo off
title AI Infra Monitor - Servidor de Monitoreo Local (Org {org_id})
color 0A
echo ========================================================
echo   AI Infra Monitor - Servidor de Monitoreo Local
echo   Organizacion ID: {org_id}
echo   Generado para tu cuenta. No compartas este archivo.
echo ========================================================
echo Conectando con la Organizacion ID: {org_id}...
set BACKEND_URL={backend_url}
set AGENT_ORG_ID={org_id}
set AGENT_TOKEN={agent_token}

python -c "import urllib.request; urllib.request.urlretrieve('%BACKEND_URL%/agent/standalone_agent.py', 'standalone_agent.py')" 2>nul
if not exist standalone_agent.py (
    powershell -Command "Invoke-WebRequest -Uri '%BACKEND_URL%/agent/standalone_agent.py' -OutFile 'standalone_agent.py'" 2>nul
)
if not exist standalone_agent.py (
    curl -s "%BACKEND_URL%/agent/standalone_agent.py" -o standalone_agent.py 2>nul
)
if not exist standalone_agent.py (
    echo [ERROR] No se pudo descargar el agente de monitoreo. Verifica tu conexion a internet.
    pause
    exit /b 1
)

echo.
echo   Servidor activado con exito para Org ID: {org_id}. Mantén esta ventana abierta.
echo.
python standalone_agent.py
pause
"""
        filename = f"iniciar_servidor_org_{org_id}.bat"
        media_type = "application/x-bat"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

