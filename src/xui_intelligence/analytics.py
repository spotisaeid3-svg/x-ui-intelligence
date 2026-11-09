"""Pure snapshot analytics: counter rates and resource threshold alerts.

This module performs no I/O and never handles client identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AlertThresholds:
    cpu_warning: float = 85.0
    cpu_critical: float = 95.0
    memory_warning: float = 90.0
    memory_critical: float = 97.0
    disk_warning: float = 85.0
    disk_critical: float = 95.0


def _rate_map(
    previous: dict[str, Any],
    current: dict[str, Any],
    elapsed_seconds: float,
) -> tuple[dict[str, float], list[str]]:
    rates: dict[str, float] = {}
    resets: list[str] = []
    if elapsed_seconds <= 0:
        return rates, resets

    for name, current_value in current.items():
        previous_value = previous.get(name)
        if not isinstance(current_value, (int, float)) or isinstance(current_value, bool):
            continue
        if not isinstance(previous_value, (int, float)) or isinstance(previous_value, bool):
            continue
        if current_value < previous_value:
            resets.append(name)
            continue
        rates[name] = round((current_value - previous_value) / elapsed_seconds, 2)
    return rates, resets


def _resource_alerts(
    snapshot: dict[str, Any],
    thresholds: AlertThresholds,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    checks = (
        ("cpu", "usage_percent", thresholds.cpu_warning, thresholds.cpu_critical),
        ("memory", "used_percent", thresholds.memory_warning, thresholds.memory_critical),
        ("disk_root", "used_percent", thresholds.disk_warning, thresholds.disk_critical),
    )
    for section, field, warning, critical in checks:
        value = snapshot.get(section, {}).get(field)
        if not isinstance(value, (int, float)):
            continue
        if value >= critical:
            severity = "critical"
        elif value >= warning:
            severity = "warning"
        else:
            continue
        alerts.append(
            {
                "severity": severity,
                "code": f"{section}_high",
                "message": f"{section} usage is {value:.1f}%",
            }
        )
    return alerts


def analyze_snapshots(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    elapsed_seconds: float | None = None,
    thresholds: AlertThresholds = AlertThresholds(),
) -> dict[str, Any]:
    """Return derived rates and threshold alerts for two consecutive snapshots.

    Counter rates are omitted for the first sample, invalid intervals, missing
    counters, and counters that decreased (e.g. after a process/interface reset).
    """
    result: dict[str, Any] = {
        "network_bytes_per_second": {},
        "xray_bytes_per_second": {},
        "counter_resets": [],
        "alerts": _resource_alerts(current, thresholds),
    }
    if previous is None or elapsed_seconds is None or elapsed_seconds <= 0:
        return result

    old_interfaces = previous.get("network_interfaces", {})
    new_interfaces = current.get("network_interfaces", {})
    if isinstance(old_interfaces, dict) and isinstance(new_interfaces, dict):
        for interface, counters in new_interfaces.items():
            old_counters = old_interfaces.get(interface, {})
            if not isinstance(counters, dict) or not isinstance(old_counters, dict):
                continue
            rates, resets = _rate_map(old_counters, counters, elapsed_seconds)
            if rates:
                result["network_bytes_per_second"][interface] = rates
            result["counter_resets"].extend(
                f"network:{interface}:{counter}" for counter in resets
            )

    old_xray = previous.get("xray", {}).get("aggregates", {})
    new_xray = current.get("xray", {}).get("aggregates", {})
    if isinstance(old_xray, dict) and isinstance(new_xray, dict):
        rates, resets = _rate_map(old_xray, new_xray, elapsed_seconds)
        result["xray_bytes_per_second"] = rates
        result["counter_resets"].extend(f"xray:{counter}" for counter in resets)

    return result
