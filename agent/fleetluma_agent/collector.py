"""Collect bounded, non-sensitive host metrics using psutil."""
from datetime import datetime, timezone
import time
import psutil


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def collect_metrics(disk_path):
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(str(disk_path))
    return {
        "cpu_pct": round(psutil.cpu_percent(interval=0.1), 2),
        "ram_used_bytes": memory.used,
        "ram_total_bytes": memory.total,
        "disk_path": str(disk_path),
        "disk_used_bytes": disk.used,
        "disk_total_bytes": disk.total,
    }


def collect_processes(limit=10):
    """Return only PID, name, per-process CPU and resident memory.

    Processes may disappear or become inaccessible while we sample them.
    The CPU sample is over a short interval, not the first unprimed reading.
    """
    candidates = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = proc.info
            memory = info["memory_info"]
            proc.cpu_percent(interval=None)
            candidates.append((proc, int(info["pid"]), info["name"] or "unknown",
                               max(0, memory.rss if memory else 0)))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    time.sleep(0.1)
    items = []
    for proc, pid, name, memory in candidates:
        try:
            cpu = max(0.0, proc.cpu_percent(interval=None))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        items.append({"pid": pid, "name": name, "cpu_pct": round(cpu, 2),
                      "memory_bytes": memory})
    return sorted(items, key=lambda x: (x["cpu_pct"], x["memory_bytes"]), reverse=True)[:limit]


def build_report(disk_path, include_processes=True):
    result = {"sampled_at": utcnow(), "metrics": collect_metrics(disk_path)}
    if include_processes:
        result["processes"] = collect_processes()
    return result
