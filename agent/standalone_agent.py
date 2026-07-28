"""
AI Infra Monitor - Standalone One-Liner Agent
Portable, zero-setup monitoring agent that runs on any machine (Windows, Linux, macOS).
"""

import os
import sys
import time
import json
import socket
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone

try:
    import psutil
except ImportError:
    print("Installing required package: psutil...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
    import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [AI-Infra-Agent] - %(levelname)s - %(message)s"
)
logger = logging.getLogger("StandaloneAgent")

BACKEND_URL = os.getenv("BACKEND_URL", "https://ai-infra-monitor-api.onrender.com").rstrip("/")
INTERVAL = int(os.getenv("AGENT_INTERVAL", "3"))

...

            elapsed = time.monotonic() - timer_start
            if len(buffer) >= 1 or elapsed >= 3:

WINDOWS_SYSTEM_PROCESSES = {
    'System', 'Registry', 'smss.exe', 'csrss.exe', 'wininit.exe',
    'services.exe', 'lsass.exe', 'svchost.exe', 'winlogon.exe',
    'dwm.exe', 'fontdrvhost.exe', 'WUDFHost.exe', 'conhost.exe',
    'RuntimeBroker.exe', 'taskhostw.exe', 'sihost.exe', 'ctfmon.exe',
    'SearchIndexer.exe', 'SearchHost.exe', 'StartMenuExperienceHost.exe',
    'ShellExperienceHost.exe', 'TextInputHost.exe', 'SecurityHealthService.exe',
    'MsMpEng.exe', 'NisSrv.exe', 'SgrmBroker.exe', 'audiodg.exe',
    'System Idle Process'
}


def collect_metrics():
    """Collect CPU, RAM, Disk, Net metrics."""
    cpu_percent = psutil.cpu_percent(interval=1)
    mem_percent = psutil.virtual_memory().percent
    
    try:
        is_win = os.name == 'nt'
        disk = psutil.disk_usage('C:\\' if is_win else '/')
        disk_percent = disk.percent
        disk_free_gb = round(disk.free / (1024 ** 3), 2)
        disk_total_gb = round(disk.total / (1024 ** 3), 2)
    except Exception:
        disk_percent, disk_free_gb, disk_total_gb = 0, 0, 0

    try:
        net_io = psutil.net_io_counters()
        net_sent = net_io.bytes_sent
        net_recv = net_io.bytes_recv
    except Exception:
        net_sent, net_recv = 0, 0

    return [
        {"metric": "cpu_percent", "value": cpu_percent},
        {"metric": "mem_percent", "value": mem_percent},
        {"metric": "disk_percent", "value": disk_percent},
        {"metric": "disk_free_gb", "value": disk_free_gb},
        {"metric": "disk_total_gb", "value": disk_total_gb},
        {"metric": "net_bytes_sent", "value": net_sent},
        {"metric": "net_bytes_recv", "value": net_recv}
    ]


def collect_process_metrics():
    """Collect top process metrics."""
    process_list = []
    try:
        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'status']):
            try:
                pinfo = proc.info
                name = pinfo['name'] or 'unknown'
                if name in WINDOWS_SYSTEM_PROCESSES:
                    continue
                proc.cpu_percent(interval=None)
                procs.append(proc)
            except Exception:
                continue

        time.sleep(0.2)

        for proc in procs:
            try:
                name = proc.info['name']
                pid = proc.info['pid']
                status = proc.info['status']
                cpu = round(proc.cpu_percent(interval=None), 2)
                mem_mb = round(proc.memory_info().rss / (1024 * 1024), 2)
                process_list.append({
                    "name": name,
                    "pid": pid,
                    "cpu_percent": cpu,
                    "memory_mb": mem_mb,
                    "status": status
                })
            except Exception:
                continue

        process_list.sort(key=lambda p: (p['cpu_percent'], p['memory_mb']), reverse=True)
        return process_list[:10]
    except Exception as e:
        logger.warning(f"Error collecting process metrics: {e}")
        return []


def http_post(url, data_dict):
    """Send JSON payload using standard urllib."""
    json_bytes = json.dumps(data_dict).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=json_bytes,
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))


def auto_register_host():
    """Find or register host ID."""
    hostname = socket.gethostname()
    try:
        req = urllib.request.Request(f"{BACKEND_URL}/api/v1/hosts")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for host in data.get("hosts", []):
                if host.get("hostname") == hostname:
                    return host.get("id")
    except Exception as e:
        logger.warning(f"Could not auto-fetch host_id: {e}")
    return 1


def main():
    hostname = socket.gethostname()
    print("=" * 60)
    print(" 🚀 AI Infra Monitor - Agente de Monitoreo en Vivo")
    print(f" 🖥️ Host: {hostname}")
    print(f" 🌐 Backend: {BACKEND_URL}")
    print("=" * 60)
    
    host_id = auto_register_host()
    logger.info(f"Iniciando telemetría para Host ID: {host_id} (intervalo: {INTERVAL}s)...")
    
    buffer = []
    timer_start = time.monotonic()
    
    while True:
        try:
            sample = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": collect_metrics(),
                "processes": collect_process_metrics()
            }
            buffer.append(sample)
            
            elapsed = time.monotonic() - timer_start
            if len(buffer) >= 1 or elapsed >= 3:
                batch = {
                    "host_id": host_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "interval": INTERVAL,
                    "samples": buffer
                }
                res = http_post(f"{BACKEND_URL}/api/v1/ingest/metrics", batch)
                logger.info(f"⚡ Telemetría enviada con éxito ({len(buffer)} muestras): {res.get('status', 'ok')}")
                buffer = []
                timer_start = time.monotonic()
                
            time.sleep(INTERVAL)
        except KeyboardInterrupt:
            print("\nAgente detenido por el usuario.")
            break
        except Exception as e:
            logger.error(f"Error en bucle de telemetría: {e}")
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
