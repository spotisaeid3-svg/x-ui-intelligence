"""Read-only Xray StatsService collector through the fixed Xray CLI subcommand."""

from __future__ import annotations

import ipaddress
import json
import subprocess
from collections import defaultdict
from typing import Any


class XrayStatsError(RuntimeError):
    """Raised when Xray stats cannot be queried or parsed."""


def _validate_loopback_address(address: str) -> None:
    if address == "localhost":
        return
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as exc:
        raise ValueError("Xray API address must be localhost or a loopback IP") from exc
    if not parsed.is_loopback:
        raise ValueError("Xray API must remain bound to a loopback address")


class XrayStatsCollector:
    """Query stats without resetting counters or invoking a shell."""

    def __init__(
        self,
        binary: str = "/usr/local/x-ui/bin/xray",
        address: str = "127.0.0.1",
        port: int = 62789,
        timeout_seconds: int = 5,
    ) -> None:
        if not binary.startswith("/"):
            raise ValueError("Xray binary path must be absolute")
        _validate_loopback_address(address)
        if not 1 <= port <= 65535:
            raise ValueError("Xray API port must be between 1 and 65535")
        if not 1 <= timeout_seconds <= 30:
            raise ValueError("timeout_seconds must be between 1 and 30")
        self.binary = binary
        self.address = address
        self.port = port
        self.timeout_seconds = timeout_seconds

    def collect(self) -> dict[str, Any]:
        command = [
            self.binary,
            "api",
            "statsquery",
            f"--server={self.address}:{self.port}",
            "-pattern",
            "",
            "-reset=false",
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise XrayStatsError(f"Unable to query Xray StatsService: {exc}") from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[:300]
            raise XrayStatsError(
                f"Xray statsquery exited with status {result.returncode}: {detail}"
            )

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise XrayStatsError("Xray statsquery did not return valid JSON") from exc

        rows = payload.get("stat", payload.get("stats", []))
        if not isinstance(rows, list):
            raise XrayStatsError("Unexpected Xray stats response structure")

        totals: dict[str, int] = defaultdict(int)
        counters_seen = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = row.get("name")
            value = row.get("value")
            if not isinstance(name, str):
                continue
            try:
                numeric_value = int(value)
            except (TypeError, ValueError):
                continue
            if numeric_value < 0:
                continue

            parts = name.split(">>>")
            if len(parts) < 4 or parts[-2] != "traffic":
                continue
            scope = parts[0]
            direction = parts[-1]
            if scope not in {"user", "inbound", "outbound"}:
                continue
            if direction not in {"uplink", "downlink"}:
                continue

            # Aggregate by class only. Do not persist usernames, UUIDs, or tags.
            totals[f"{scope}_{direction}_bytes"] += numeric_value
            counters_seen += 1

        return {
            "available": True,
            "counters_seen": counters_seen,
            "aggregates": dict(sorted(totals.items())),
        }
