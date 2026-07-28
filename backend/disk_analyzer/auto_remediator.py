"""
Disk Analyzer AI - Automated Unattended Auto-Remediator Engine (90% Disk Occupancy Bot)

Automatically triggers zero-risk cleanup operations when a host's disk occupancy reaches or exceeds 90.0%.
Executes backup, logs B2B audit traceability, and dispatches real-time Webhook notifications.
"""

import os
import json
import logging
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from backend.disk_analyzer.scanner import DiskScanner
from backend.disk_analyzer.cleaner import DiskCleaner
from backend.app.notifications_dispatcher import NotificationDispatcher

logger = logging.getLogger(__name__)


def get_db_connection():
    try:
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
    except Exception as e:
        logger.error(f"Database connection error in auto_remediator: {e}")
        return None


class AutoRemediator:
    """Automated Bot for zero-risk auto-remediation at 90% disk threshold."""

    @classmethod
    async def check_and_execute(cls, host_id: int, org_id: int = 1, current_disk_percent: float = 90.0) -> Dict[str, Any]:
        """Check threshold and execute unattended cleanup if disk >= 90%."""
        if current_disk_percent < 90.0:
            return {"triggered": False, "reason": f"Disk occupancy ({current_disk_percent}%) below 90% threshold."}

        # Check org settings
        settings = NotificationDispatcher.get_org_settings(org_id)
        if not settings.get("auto_remediation_enabled", True):
            logger.info(f"Auto-remediation disabled for org_id={org_id}")
            return {"triggered": False, "reason": "Auto-remediation policy disabled by organization."}

        conn = get_db_connection()
        if not conn:
            return {"triggered": False, "reason": "Database connection failed"}

        try:
            cursor = conn.cursor()

            # Prevent duplicate auto-remediations within 15 minutes
            cursor.execute("""
                SELECT executed_at FROM cleanup_audit_logs
                WHERE host_id = %s AND ai_provider = 'BOT_AUTO_REMEDIATION_90'
                ORDER BY executed_at DESC LIMIT 1;
            """, (host_id,))
            row = cursor.fetchone()
            if row and row[0]:
                last_exec = row[0]
                if datetime.now() - last_exec < timedelta(minutes=15):
                    logger.info(f"Skipping auto-remediation: executed recently at {last_exec}")
                    return {"triggered": False, "reason": "Auto-remediation throttled (ran within last 15 minutes)."}

            logger.info(f"🚨 CRITICAL DISK ({current_disk_percent}%): Triggering Auto-Remediator Bot on Host #{host_id}...")

            # Run scanner
            scanner = DiskScanner(host_id, drive="C:")
            scan_results = scanner.scan_all_categories()
            categories = scan_results.get("categories", {})

            # Target 100% zero-risk safe categories
            safe_categories = ["temp_files", "browser_cache", "recycle_bin"]
            files_to_clean = []
            bytes_to_free = 0

            for cat_name in safe_categories:
                cat_data = categories.get(cat_name, {})
                for f_info in cat_data.get("files", []):
                    files_to_clean.append({
                        "path": f_info.get("path"),
                        "size": f_info.get("size", 0),
                        "category": cat_name
                    })
                    bytes_to_free += f_info.get("size", 0)

            if not files_to_clean:
                logger.info("Auto-remediator scan completed: no zero-risk temporary files found to delete.")
                return {"triggered": True, "files_deleted": 0, "bytes_freed": 0, "formatted_freed": "0 B"}

            # Execute cleaner
            cleaner = DiskCleaner(host_id=host_id, scan_id=0)
            cleanup_res = cleaner.cleanup_categories(safe_categories, categories, create_backup=True)

            deleted_count = cleanup_res.get("files_deleted_count", len(files_to_clean))
            bytes_freed = cleanup_res.get("total_bytes_freed", bytes_to_free)
            backup_path = cleanup_res.get("backup_path", "")
            formatted_freed = DiskCleaner._format_size(bytes_freed)

            # Record B2B Immutable Audit Log
            cursor.execute("""
                INSERT INTO cleanup_audit_logs 
                (org_id, host_id, user_id, categories, files_deleted_count, bytes_freed, backup_path, ai_provider, ai_analysis_summary)
                VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s);
            """, (
                org_id,
                host_id,
                safe_categories,
                deleted_count,
                bytes_freed,
                backup_path,
                "BOT_AUTO_REMEDIATION_90",
                f"Auto-Remediador Desatendida ejecutado por ocupación al {current_disk_percent:.1f}%. Se liberaron {formatted_freed} en 3 categorías de cero riesgo."
            ))
            conn.commit()
            cursor.close()

            # Dispatch notification
            await NotificationDispatcher.send_webhook(
                webhook_url=settings.get("webhook_url", ""),
                title=f"🤖 Auto-Remediación Desatendida Ejecutada (Host #{host_id})",
                message=f"El disco alcanzó un {current_disk_percent:.1f}% de ocupación. El bot intervino automáticamente y liberó {formatted_freed} de archivos temporales de forma 100% segura.",
                severity="HIGH",
                host_info=f"Host #{host_id}"
            )

            logger.info(f"✅ Auto-remediation completed: freed {formatted_freed} across {deleted_count} files.")
            return {
                "triggered": True,
                "files_deleted": deleted_count,
                "bytes_freed": bytes_freed,
                "formatted_freed": formatted_freed,
                "backup_path": backup_path
            }

        except Exception as e:
            logger.error(f"Error executing auto-remediation: {e}")
            return {"triggered": False, "reason": str(e)}
        finally:
            if conn:
                conn.close()
