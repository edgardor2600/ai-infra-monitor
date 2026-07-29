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

import ssl
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass

BACKEND_URL = os.getenv("BACKEND_URL", "https://ai-infra-monitor-api.onrender.com").rstrip("/")
INTERVAL = int(os.getenv("AGENT_INTERVAL", "3"))

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
        
        # Register via POST if not found
        org_id = int(os.getenv("AGENT_ORG_ID", "1"))
        reg_payload = json.dumps({"hostname": hostname, "org_id": org_id}).encode('utf-8')
        reg_req = urllib.request.Request(
            f"{BACKEND_URL}/api/v1/hosts/register",
            data=reg_payload,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(reg_req, timeout=10) as reg_resp:
            reg_data = json.loads(reg_resp.read().decode('utf-8'))
            return reg_data.get("id", 1)
    except Exception as e:
        logger.warning(f"Could not auto-fetch or register host_id: {e}")
    return 1


def scan_local_cleanup_paths():
    """Perform real disk cleanup scan on local machine."""
    is_win = os.name == 'nt'
    user_home = os.path.expanduser('~')
    
    paths_map = {
        'temp_files': {
            'display_name': 'Archivos Temporales',
            'description': 'Archivos y carpetas temporales de sistema y aplicaciones.',
            'risk_level': 'low',
            'is_safe_auto': True,
            'check_paths': [
                os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Temp') if is_win else '/tmp',
                os.path.join(user_home, 'AppData', 'Local', 'Temp') if is_win else '/var/tmp'
            ]
        },
        'browser_cache': {
            'display_name': 'Caché de Navegadores',
            'description': 'Imágenes y recursos almacenados por Chrome y Edge.',
            'risk_level': 'low',
            'is_safe_auto': True,
            'check_paths': [
                os.path.join(user_home, 'AppData', 'Local', 'Google', 'Chrome', 'User Data', 'Default', 'Cache') if is_win else os.path.join(user_home, '.cache', 'google-chrome'),
                os.path.join(user_home, 'AppData', 'Local', 'Microsoft', 'Edge', 'User Data', 'Default', 'Cache') if is_win else None
            ]
        },
        'pkg_managers': {
            'display_name': 'Caché de Gestores de Paquetes',
            'description': 'Caché acumulado de pip, npm y yarn.',
            'risk_level': 'medium',
            'is_safe_auto': False,
            'check_paths': [
                os.path.join(user_home, 'AppData', 'Local', 'pip', 'Cache') if is_win else os.path.join(user_home, '.cache', 'pip'),
                os.path.join(user_home, 'AppData', 'Local', 'npm-cache') if is_win else os.path.join(user_home, '.npm', '_cacache')
            ]
        },
        'system_logs': {
            'display_name': 'Logs del Sistema',
            'description': 'Informes de eventos antiguos y volcados de memoria.',
            'risk_level': 'low',
            'is_safe_auto': True,
            'check_paths': [
                os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Logs') if is_win else '/var/log'
            ]
        }
    }
    
    categories_res = {}
    total_size_bytes = 0
    
    for cat_id, cat_meta in paths_map.items():
        cat_files = []
        cat_size = 0
        cat_count = 0
        
        for folder_path in cat_meta['check_paths']:
            if not folder_path or not os.path.exists(folder_path):
                continue
            try:
                for root, _, files in os.walk(folder_path):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            fsize = os.path.getsize(fp)
                            cat_size += fsize
                            cat_count += 1
                            if len(cat_files) < 10:
                                cat_files.append({
                                    "path": fp,
                                    "size": fsize,
                                    "is_safe": cat_meta['is_safe_auto'],
                                    "risk_level": cat_meta['risk_level']
                                })
                        except Exception:
                            continue
            except Exception:
                continue
                
        total_size_bytes += cat_size
        categories_res[cat_id] = {
            "display_name": cat_meta['display_name'],
            "description": cat_meta['description'],
            "risk_level": cat_meta['risk_level'],
            "is_safe_auto": cat_meta['is_safe_auto'],
            "total_size": cat_size,
            "file_count": cat_count,
            "files": cat_files
        }
        
    return categories_res, total_size_bytes


def main():
    hostname = socket.gethostname()
    print("=" * 60)
    print(" 🚀 AI Infra Monitor - Agente de Monitoreo en Vivo")
    print(f" 🖥️ Host: {hostname}")
    print(f" 🌐 Backend: {BACKEND_URL}")
    print("=" * 60)
    
    host_id = auto_register_host()
    logger.info(f"Iniciando telemetría para Host ID: {host_id} (intervalo: {INTERVAL}s)...")
    
    # Perform initial real local disk scan for this machine
    try:
        logger.info("Realizando escaneo local de disco inicial en el equipo...")
        cat_res, tot_size = scan_local_cleanup_paths()
        org_id = int(os.getenv("AGENT_ORG_ID", "1"))
        scan_payload = {
            "host_id": host_id,
            "org_id": org_id,
            "drive": "C:" if os.name == 'nt' else "/",
            "total_size_bytes": tot_size,
            "categories": cat_res
        }
        http_post(f"{BACKEND_URL}/api/v1/disk-analyzer/agent-scan-results", scan_payload)
        logger.info(f"🔍 Escaneo de disco enviado con éxito: {tot_size} bytes en categorías reales.")
    except Exception as e:
        logger.warning(f"No se pudo enviar escaneo inicial de disco: {e}")

    while True:
        try:
            metrics = collect_metrics()
            processes = collect_process_metrics()
            
            batch = {
                "host_id": host_id,
                "hostname": hostname,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "interval": INTERVAL,
                "samples": metrics,
                "processes": processes
            }
            res = http_post(f"{BACKEND_URL}/api/v1/ingest/metrics", batch)
            logger.info(f"⚡ Telemetría enviada con éxito ({len(metrics)} métricas, {len(processes)} procesos): {res.get('status', 'ok')}")
            time.sleep(INTERVAL)
        except KeyboardInterrupt:
            print("\nAgente detenido por el usuario.")
            break
        except Exception as e:
            logger.error(f"Error en bucle de telemetría: {e}")
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
