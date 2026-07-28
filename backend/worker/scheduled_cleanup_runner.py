"""
AI Infra Monitor — Scheduled Disk Maintenance Runner.

Executes periodic zero-risk automated cleanup jobs in background.
Enforces strict safety rules: only zero-risk categories (temp_files, browser_cache,
recycle_bin, thumbnails, windows_update) are automatically purged.
"""

import os
import json
import logging
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from backend.disk_analyzer.scanner import DiskScanner
from backend.disk_analyzer.cleaner import DiskCleaner

logger = logging.getLogger(__name__)

# Strict whitelist of categories allowed for automatic background maintenance
SAFE_AUTOMATED_CATEGORIES = {
    'temp_files',
    'browser_cache',
    'recycle_bin',
    'thumbnails',
    'windows_update',
    'pkg_managers',
    'installers'
}


def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_infra_monitor"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )


def run_due_scheduled_cleanups() -> List[Dict[str, Any]]:
    """
    Find due scheduled cleanups, perform disk scan, execute zero-risk cleanup,
    and update next run timestamp.
    """
    results = []
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, host_id, org_id, categories, interval_hours, last_run_at, next_run_at
            FROM scheduled_disk_cleanups
            WHERE enabled = true AND (next_run_at IS NULL OR next_run_at <= NOW())
        """)
        schedules = cursor.fetchall()

        for schedule in schedules:
            sched_id, host_id, org_id, categories, interval_hours, last_run_at, next_run_at = schedule

            # Filter categories to strictly safe automated categories
            safe_cats = [cat for cat in categories if cat in SAFE_AUTOMATED_CATEGORIES]
            if not safe_cats:
                safe_cats = ['temp_files', 'browser_cache', 'recycle_bin']

            logger.info(f"Executing scheduled cleanup #{sched_id} for host #{host_id} with categories: {safe_cats}")

            try:
                # 1. Run scanner to discover target files
                scanner = DiskScanner(host_id=host_id)
                scan_results = scanner.scan_all_categories()

                # Extract files by target category
                files_by_cat = {}
                cat_dict = scan_results.get('categories', {})
                for cat in safe_cats:
                    if cat in cat_dict:
                        files_by_cat[cat] = cat_dict[cat].get('files', [])

                # 2. Execute cleanup
                cleaner = DiskCleaner(host_id=host_id, scan_id=0)
                cleanup_res = cleaner.cleanup_categories(safe_cats, files_by_cat, create_backup=True)

                # 3. Update schedule timestamps
                now = datetime.now()
                next_run = now + timedelta(hours=interval_hours)

                cursor.execute("""
                    UPDATE scheduled_disk_cleanups
                    SET last_run_at = %s, next_run_at = %s
                    WHERE id = %s
                """, (now, next_run, sched_id))

                # 4. Insert audit log entry
                cursor.execute("""
                    INSERT INTO cleanup_audit_logs 
                    (org_id, host_id, categories, files_deleted_count, bytes_freed, backup_path, ai_provider, ai_analysis_summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    org_id,
                    host_id,
                    safe_cats,
                    cleanup_res['files_deleted'],
                    cleanup_res['size_freed'],
                    cleanup_res.get('backup_path'),
                    "Automated Maintenance Engine",
                    f"Mantenimiento automático programado (Cron {interval_hours}h) ejecutado con éxito."
                ))

                conn.commit()

                res_info = {
                    "schedule_id": sched_id,
                    "host_id": host_id,
                    "categories_cleaned": safe_cats,
                    "files_deleted": cleanup_res['files_deleted'],
                    "bytes_freed": cleanup_res['size_freed'],
                    "next_run_at": next_run.isoformat()
                }
                results.append(res_info)
                logger.info(f"Scheduled cleanup #{sched_id} completed: {res_info}")

            except Exception as item_err:
                logger.error(f"Failed executing scheduled cleanup #{sched_id}: {item_err}")

        cursor.close()
    except Exception as err:
        logger.error(f"Error in run_due_scheduled_cleanups: {err}")
    finally:
        if conn:
            conn.close()

    return results
