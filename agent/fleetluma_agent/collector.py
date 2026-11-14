"""Collect non-sensitive machine metrics for the FleetLuma contract."""
from datetime import datetime, timezone
from pathlib import Path
import psutil


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def collect_metrics(disk_path):
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(str(disk_path))
    return {
        "cpu_pct": round(psutil.cpu_percent(interval=0.1), 2),
        "ram_used_bytes": mem.used,
        "ram_total_bytes": mem.total,
        "disk_path": str(disk_path),
        "disk_used_bytes": disk.used,
        "disk_total_bytes": disk.total,
    }


def collect_processes(limit=10):
    """Process metadata only, no cmdline, environment or remote control."""
    results = []
    for process in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            item = process.info
            memory = item["memory_info"]
            # psutil per-process CPU needs priming; estimate CPU over a short interval.
            process.cpu_percent(interval=None)
            results.append((process, item["pid"], item["name"] or "unknown",
                            memory.rss if memory is not None else 0))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    psutil.cpu_percent(interval=0.1)
    for process, pid, name, memory in results:
        try:
            cpu = max(0.0, process.cpu_percent(interval=None))
            results_cpu = cpu
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            results_cpu = 0.0
        yield_value = {"pid": pid, "name": name, "cpu_pct": round(results_cpu, 2),
                       "memory_bytes": memory}
        results_cpu = None
        if "items" not in locals():
            items = []
        items.append(yield_value)
    items = locals().get("items", [])
    return sorted(items, key=lambda x: (x["cpu_pct"], x["memory_bytes"]), reverse=True)[:limit]


def build_report(disk_path, include_processes=True):
    report = {"sampled_at": utcnow(), "metrics": collect_metrics(disk_path)}
    if include_processes:
        report["processes"] = collect_processes()
    return report
