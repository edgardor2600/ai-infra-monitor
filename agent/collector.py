"""
AI Infra Monitor Agent - Collector Module

This module provides functions to collect system metrics using psutil.
"""

import logging
import psutil
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Windows system processes to exclude from monitoring
WINDOWS_SYSTEM_PROCESSES = {
    'System', 'Registry', 'smss.exe', 'csrss.exe', 'wininit.exe',
    'services.exe', 'lsass.exe', 'svchost.exe', 'winlogon.exe',
    'dwm.exe', 'fontdrvhost.exe', 'WUDFHost.exe', 'conhost.exe',
    'RuntimeBroker.exe', 'taskhostw.exe', 'sihost.exe', 'ctfmon.exe',
    'SearchIndexer.exe', 'SearchHost.exe', 'StartMenuExperienceHost.exe',
    'ShellExperienceHost.exe', 'TextInputHost.exe', 'SecurityHealthService.exe',
    'MsMpEng.exe', 'NisSrv.exe', 'SgrmBroker.exe', 'audiodg.exe',
    'System Idle Process'  # Virtual process, not useful for monitoring
}


def collect_once() -> Dict[str, Any]:
    """
    Usa psutil para obtener métricas básicas.
    
    Devuelve un diccionario con:
    {
        "metric": "<nombre>",
        "value": <float|int>
    }
    
    Returns:
        Dict[str, Any]: Dictionary containing metric name and value
    """
    logger.info("Collecting metrics using psutil")
    
    # Collect CPU percentage (non-blocking, interval=1 for accuracy)
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Collect memory percentage
    mem_percent = psutil.virtual_memory().percent
    
    # Collect disk usage (for C: drive on Windows, / on Linux)
    try:
        disk = psutil.disk_usage('C:\\' if psutil.WINDOWS else '/')
        disk_percent = disk.percent
        disk_free_gb = disk.free / (1024 ** 3)  # Convert to GB
        disk_total_gb = disk.total / (1024 ** 3)
    except Exception as e:
        logger.warning(f"Failed to collect disk metrics: {e}")
        disk_percent = 0
        disk_free_gb = 0
        disk_total_gb = 0
    
    # Collect network I/O
    try:
        net_io = psutil.net_io_counters()
        net_bytes_sent = net_io.bytes_sent
        net_bytes_recv = net_io.bytes_recv
    except Exception as e:
        logger.warning(f"Failed to collect network metrics: {e}")
        net_bytes_sent = 0
        net_bytes_recv = 0
    
    # Return as list of samples
    samples = [
        {"metric": "cpu_percent", "value": cpu_percent},
        {"metric": "mem_percent", "value": mem_percent},
        {"metric": "disk_percent", "value": disk_percent},
        {"metric": "disk_free_gb", "value": round(disk_free_gb, 2)},
        {"metric": "disk_total_gb", "value": round(disk_total_gb, 2)},
        {"metric": "net_bytes_sent", "value": net_bytes_sent},
        {"metric": "net_bytes_recv", "value": net_bytes_recv}
    ]
    
    logger.info(f"Collected {len(samples)} metrics")
    return samples


def collect_process_metrics() -> List[Dict[str, Any]]:
    """
    Collect metrics for individual processes.
    
    Returns top 10 processes by CPU and memory usage, excluding Windows system processes.
    
    Returns:
        List[Dict[str, Any]]: List of process metrics with name, pid, cpu_percent, memory_mb, status
    """
    logger.info("Collecting process metrics")
    
    process_list = []
    
    try:
        # First pass: Initialize CPU percent for all processes
        # This is needed because cpu_percent() returns 0.0 on first call
        processes_to_monitor = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'status']):
            try:
                # Initialize CPU percent (this call returns 0.0 but sets up monitoring)
                proc.cpu_percent(interval=None)
                processes_to_monitor.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # Wait a bit to let CPU measurements accumulate
        import time
        time.sleep(0.5)
        
        # Second pass: Collect actual metrics
        for proc in processes_to_monitor:
            try:
                # Get process info
                pinfo = proc.info
                process_name = pinfo['name']
                
                # Skip processes with empty names (some Windows processes don't have names)
                if not process_name or process_name.strip() == '':
                    continue
                
                # Skip Windows system processes
                if process_name in WINDOWS_SYSTEM_PROCESSES:
                    continue
                
                # Get CPU percent (now this should return actual values)
                # Note: psutil returns CPU% per-core, so we need to normalize it
                # by dividing by the number of CPU cores to get a 0-100% range
                cpu_percent_raw = proc.cpu_percent(interval=None) or 0.0
                cpu_cores = psutil.cpu_count()
                cpu_percent = cpu_percent_raw / cpu_cores if cpu_cores else cpu_percent_raw
                
                # Get memory in MB
                memory_mb = 0.0
                if pinfo['memory_info']:
                    memory_mb = pinfo['memory_info'].rss / (1024 * 1024)  # Convert bytes to MB
                
                # Get status, default to 'unknown' if not available
                status = pinfo['status'] or 'unknown'
                if not status or status.strip() == '':
                    status = 'unknown'
                
                # Only include processes with significant resource usage
                if cpu_percent > 0.1 or memory_mb > 50:
                    process_list.append({
                        'name': process_name,
                        'pid': pinfo['pid'],
                        'cpu_percent': round(cpu_percent, 2),
                        'memory_mb': round(memory_mb, 2),
                        'status': status
                    })
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Skip processes that disappeared or we can't access
                continue
        
        # Sort by CPU usage and get top 10
        top_cpu = sorted(process_list, key=lambda x: x['cpu_percent'], reverse=True)[:10]
        
        # Sort by memory usage and get top 10
        top_memory = sorted(process_list, key=lambda x: x['memory_mb'], reverse=True)[:10]
        
        # Combine and deduplicate (use dict to maintain order and remove duplicates by PID)
        combined = {p['pid']: p for p in top_cpu + top_memory}
        result = list(combined.values())
        
        logger.info(f"Collected {len(result)} process metrics (top by CPU and memory)")
        return result
        
    except Exception as e:
        logger.error(f"Error collecting process metrics: {e}")
        return []
