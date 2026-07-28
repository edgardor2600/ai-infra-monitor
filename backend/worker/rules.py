"""
AI Infra Monitor — Intelligent Alert Rules Engine v2

Seven context-aware rules designed to eliminate alert fatigue by catching
real problems with proper thresholds, metadata and actionable recommendations.

Each rule returns an enriched RuleResult dict or None if the condition is fine.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class RuleResult:
    """Standardized output from any alert rule evaluation."""
    rule_name: str
    metric: str
    severity: str          # CRITICAL | HIGH | MEDIUM | LOW | INFO
    message: str
    threshold_value: float
    actual_value: float
    recommendation: str
    auto_resolvable: bool = True   # Can this alert auto-resolve when metric normalizes?
    cooldown_minutes: int = 5      # Min gap between creating new alert records


def rule_cpu_sustained(avg_30s: float, avg_180s: float) -> Optional[RuleResult]:
    """
    CPU SUSTAINED: Fires only when CPU is elevated for 3+ minutes continuously,
    not on momentary spikes (compiling, updates, etc.).

    Uses the 3-minute average to filter out transient CPU bursts.
    Severity escalates: 85%=HIGH, 95%=CRITICAL.
    """
    if avg_180s <= 0:
        return None  # Not enough history yet

    severity = None
    if avg_180s >= 95:
        severity = "CRITICAL"
    elif avg_180s >= 85:
        severity = "HIGH"

    if severity:
        return RuleResult(
            rule_name="cpu_sustained",
            metric="cpu_percent",
            severity=severity,
            message=(
                f"CPU usage sustained at {avg_180s:.1f}% for 3+ minutes "
                f"(current 30s avg: {avg_30s:.1f}%)"
            ),
            threshold_value=85.0,
            actual_value=avg_180s,
            recommendation=(
                "Open Task Manager → Processes sorted by CPU. "
                "Identify the top consumer. If it's a build or update process, "
                "it may self-resolve. If it's an unknown process, investigate immediately."
            ),
            cooldown_minutes=10,
        )
    return None


def rule_cpu_anomaly_spike(avg_30s: float, baseline_avg: float) -> Optional[RuleResult]:
    """
    CPU ANOMALY SPIKE: Detects sudden spikes vs. historical baseline of same host.
    Fires when current 30s avg is 200%+ higher than the last-hour baseline,
    but only if the baseline was below 50% (to avoid false positives on busy servers).
    """
    if baseline_avg <= 0 or baseline_avg >= 50:
        return None

    if avg_30s <= 0:
        return None

    delta_pct = ((avg_30s - baseline_avg) / baseline_avg) * 100

    if delta_pct > 200:
        return RuleResult(
            rule_name="cpu_anomaly_spike",
            metric="cpu_percent",
            severity="MEDIUM",
            message=(
                f"Unexpected CPU spike: {avg_30s:.1f}% vs. baseline {baseline_avg:.1f}% "
                f"(+{delta_pct:.0f}% increase)"
            ),
            threshold_value=baseline_avg * 3,
            actual_value=avg_30s,
            recommendation=(
                "A sudden CPU spike from a low baseline usually indicates a background task, "
                "scheduled job, or rogue process starting up. Check running processes "
                "and correlate with scheduled tasks or deployments."
            ),
        )
    return None


def rule_memory_critical(mem_used_pct: float, mem_free_mb: float) -> Optional[RuleResult]:
    """
    MEMORY CRITICAL: Fires when the system is at or near memory exhaustion.
    Free memory < 300MB OR usage > 92% indicates the OS may start swapping heavily.
    """
    is_critical = mem_used_pct >= 92 or (mem_free_mb > 0 and mem_free_mb < 300)

    if is_critical:
        severity = "CRITICAL" if mem_used_pct >= 96 or mem_free_mb < 100 else "HIGH"
        return RuleResult(
            rule_name="memory_critical",
            metric="mem_percent",
            severity=severity,
            message=(
                f"Memory at critical level: {mem_used_pct:.1f}% used "
                f"({mem_free_mb:.0f} MB free). System may begin swapping."
            ),
            threshold_value=92.0,
            actual_value=mem_used_pct,
            recommendation=(
                "Identify memory-hungry processes immediately. "
                "Run: `tasklist /fo table /nh | sort /r /+65` on Windows. "
                "Consider restarting non-essential services or adding RAM. "
                "If swap is active, performance will degrade severely."
            ),
        )
    return None


def rule_memory_high_sustained(avg_mem_5min: float) -> Optional[RuleResult]:
    """
    MEMORY HIGH (SUSTAINED): Fires when RAM stays above 85% for 5+ minutes.
    Distinguishes from momentary spikes due to loading/cache warming.
    """
    if avg_mem_5min >= 85:
        return RuleResult(
            rule_name="memory_high_sustained",
            metric="mem_percent",
            severity="MEDIUM",
            message=(
                f"Memory usage sustained at {avg_mem_5min:.1f}% for 5+ minutes. "
                "Risk of memory pressure impacting application performance."
            ),
            threshold_value=85.0,
            actual_value=avg_mem_5min,
            recommendation=(
                "Monitor for memory leaks in long-running processes. "
                "Check application logs for OutOfMemory errors. "
                "Consider scheduling a memory-intensive process restart during low-traffic hours."
            ),
        )
    return None


def rule_disk_critical(
    disk_used_pct: float,
    disk_free_gb: float,
    drive: str = "C:"
) -> Optional[RuleResult]:
    """
    DISK CRITICAL: Fires when free disk space drops below 5 GB or 5% of total.
    At this level, databases, logs and system processes start failing.
    """
    is_low = disk_used_pct >= 95 or (disk_free_gb > 0 and disk_free_gb < 5.0)

    if is_low:
        severity = "CRITICAL" if disk_free_gb < 2.0 or disk_used_pct >= 98 else "HIGH"
        return RuleResult(
            rule_name="disk_critical",
            metric="disk_percent",
            severity=severity,
            message=(
                f"Disk {drive} critically low: {disk_free_gb:.1f} GB free "
                f"({disk_used_pct:.1f}% used). Database and OS operations at risk."
            ),
            threshold_value=95.0,
            actual_value=disk_used_pct,
            recommendation=(
                f"IMMEDIATE ACTION REQUIRED on drive {drive}. "
                "Run Disk Analyzer AI to identify largest consumers. "
                "Delete temp files, log archives and unused installers. "
                "If a log file is growing uncontrolled, truncate and fix the logging config."
            ),
        )
    return None


def rule_disk_trend_runaway(
    free_gb_now: float,
    free_gb_24h_ago: float,
    drive: str = "C:"
) -> Optional[RuleResult]:
    """
    DISK TREND (LOG RUNAWAY): Fires when the disk lost > 8 GB in the last 24 hours.
    This pattern typically indicates runaway log files, crash dumps or caching gone wrong.
    """
    if free_gb_24h_ago <= 0 or free_gb_now <= 0:
        return None

    gb_lost = free_gb_24h_ago - free_gb_now

    if gb_lost >= 8.0:
        rate_per_hour = gb_lost / 24
        return RuleResult(
            rule_name="disk_trend_runaway",
            metric="disk_free_gb",
            severity="HIGH",
            message=(
                f"Disk {drive} losing space rapidly: {gb_lost:.1f} GB consumed in 24h "
                f"({rate_per_hour:.1f} GB/h). Possible log runaway or crash dump accumulation."
            ),
            threshold_value=8.0,
            actual_value=gb_lost,
            recommendation=(
                f"Investigate what is consuming space on {drive} at high velocity. "
                "Check: Windows Event Logs, IIS logs, SQL Server transaction logs, "
                "application crash dumps in C:\\CrashDumps. "
                "Use Disk Analyzer AI → Treemap to locate the growing directory."
            ),
        )
    return None


def rule_host_silent(minutes_since_last_metric: float) -> Optional[RuleResult]:
    """
    HOST SILENT: Fires when a host's monitoring agent stops reporting for >5 minutes.
    Could indicate: agent crash, network issue, system reboot, or power failure.
    """
    if minutes_since_last_metric >= 5:
        severity = "CRITICAL" if minutes_since_last_metric >= 15 else "HIGH"
        return RuleResult(
            rule_name="host_silent",
            metric="agent_heartbeat",
            severity=severity,
            message=(
                f"Agent has not reported metrics for {minutes_since_last_metric:.0f} minutes. "
                "Host may be unreachable or the monitoring agent may have crashed."
            ),
            threshold_value=5.0,
            actual_value=minutes_since_last_metric,
            recommendation=(
                "1. Ping the host to verify network connectivity. "
                "2. Check if the AI Infra Monitor agent is running on the target machine. "
                "3. Review system event logs for unexpected reboots or crashes. "
                "4. Restart the agent service if the host is reachable."
            ),
            auto_resolvable=True,
            cooldown_minutes=5,
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Helper: evaluate all rules against a collected metrics snapshot
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_all_rules(metrics: Dict[str, Any]) -> List[RuleResult]:
    """
    Evaluate all 7 rules against the current metrics snapshot for a host.

    Expected metrics dict keys:
        avg_cpu_30s       float — avg CPU% over last 30 seconds
        avg_cpu_180s      float — avg CPU% over last 3 minutes
        avg_cpu_baseline  float — avg CPU% over last 1 hour (baseline)
        mem_used_pct      float — current memory usage percentage
        mem_free_mb       float — current free memory in MB
        avg_mem_5min      float — avg memory % over last 5 minutes
        disk_used_pct     float — current disk usage % for primary drive
        disk_free_gb      float — current free disk space in GB
        disk_free_gb_24h  float — free disk space 24h ago (for trend rule)
        drive             str   — drive letter (default 'C:')
        minutes_silent    float — minutes since last agent report (0 = active)

    Returns list of triggered RuleResult objects (may be empty).
    """
    results: List[RuleResult] = []

    drive = metrics.get("drive", "C:")

    # Rule 1 — CPU sustained
    r = rule_cpu_sustained(
        avg_30s=metrics.get("avg_cpu_30s", 0),
        avg_180s=metrics.get("avg_cpu_180s", 0),
    )
    if r:
        results.append(r)

    # Rule 2 — CPU anomaly spike
    r = rule_cpu_anomaly_spike(
        avg_30s=metrics.get("avg_cpu_30s", 0),
        baseline_avg=metrics.get("avg_cpu_baseline", 0),
    )
    if r:
        results.append(r)

    # Rule 3 — Memory critical
    r = rule_memory_critical(
        mem_used_pct=metrics.get("mem_used_pct", 0),
        mem_free_mb=metrics.get("mem_free_mb", 9999),
    )
    if r:
        results.append(r)

    # Rule 4 — Memory high sustained
    r = rule_memory_high_sustained(avg_mem_5min=metrics.get("avg_mem_5min", 0))
    if r:
        results.append(r)

    # Rule 5 — Disk critical
    r = rule_disk_critical(
        disk_used_pct=metrics.get("disk_used_pct", 0),
        disk_free_gb=metrics.get("disk_free_gb", 9999),
        drive=drive,
    )
    if r:
        results.append(r)

    # Rule 6 — Disk trend runaway
    r = rule_disk_trend_runaway(
        free_gb_now=metrics.get("disk_free_gb", 0),
        free_gb_24h_ago=metrics.get("disk_free_gb_24h", 0),
        drive=drive,
    )
    if r:
        results.append(r)

    # Rule 7 — Host silent
    r = rule_host_silent(minutes_since_last_metric=metrics.get("minutes_silent", 0))
    if r:
        results.append(r)

    return results
