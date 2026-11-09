"""Read-only Linux host telemetry collector based on procfs and statvfs."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any


def _read_meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
        key, _, rest = line.partition(":")
        parts = rest.strip().split()
        if parts and parts[0].isdigit():
            values[key] = int(parts[0]) * 1024
    return values


def _read_cpu_counters() -> tuple[int, int]:
    fields = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0].split()
    values = [int(value) for value in fields[1:]]
    if len(values) < 5:
        raise ValueError("Unexpected /proc/stat CPU counter format")
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return sum(values), idle


def _read_network_counters() -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for line in Path("/proc/net/dev").read_text(encoding="ascii").splitlines()[2:]:
        interface, separator, counters = line.partition(":")
        if not separator:
            continue
        name = interface.strip()
        if name == "lo":
            continue
        values = [int(value) for value in counters.split()]
        if len(values) < 16:
            continue
        result[name] = {
            "rx_bytes": values[0],
            "rx_packets": values[1],
            "tx_bytes": values[8],
            "tx_packets": values[9],
        }
    return result


class SystemCollector:
    """Stateful collector so CPU utilization can be calculated from counter deltas."""

    def __init__(self) -> None:
        self._previous_cpu: tuple[int, int] | None = None

    def collect(self) -> dict[str, Any]:
        memory = _read_meminfo()
        memory_total = memory.get("MemTotal", 0)
        memory_available = memory.get("MemAvailable", 0)

        disk = shutil.disk_usage("/")
        current_cpu = _read_cpu_counters()
        cpu_percent: float | None = None

        if self._previous_cpu is not None:
            total_delta = current_cpu[0] - self._previous_cpu[0]
            idle_delta = current_cpu[1] - self._previous_cpu[1]
            if total_delta > 0:
                cpu_percent = round(
                    max(0.0, min(100.0, (total_delta - idle_delta) * 100 / total_delta)),
                    2,
                )
        self._previous_cpu = current_cpu

        try:
            uptime_seconds = float(Path("/proc/uptime").read_text().split()[0])
        except (OSError, ValueError, IndexError):
            uptime_seconds = None

        return {
            "hostname": os.uname().nodename,
            "cpu": {
                "logical_cores": os.cpu_count(),
                "usage_percent": cpu_percent,
            },
            "memory": {
                "total_bytes": memory_total,
                "available_bytes": memory_available,
                "used_bytes": max(memory_total - memory_available, 0),
                "used_percent": (
                    round((memory_total - memory_available) * 100 / memory_total, 2)
                    if memory_total
                    else None
                ),
            },
            "disk_root": {
                "total_bytes": disk.total,
                "used_bytes": disk.used,
                "free_bytes": disk.free,
                "used_percent": (
                    round(disk.used * 100 / disk.total, 2) if disk.total else None
                ),
            },
            "load_average": list(os.getloadavg()),
            "uptime_seconds": uptime_seconds,
            "network_interfaces": _read_network_counters(),
        }
