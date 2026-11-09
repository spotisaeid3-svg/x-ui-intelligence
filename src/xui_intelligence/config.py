"""Validated TOML configuration."""

from __future__ import annotations

import ipaddress
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    poll_interval_seconds: int
    retention_days: int
    database_path: Path
    xray_enabled: bool
    xray_binary: str
    xray_address: str
    xray_port: int
    xui_database_enabled: bool
    xui_snapshot_path: Path
    xui_snapshot_max_age_seconds: int


def load_config(path: Path) -> AppConfig:
    if not path.is_file():
        raise FileNotFoundError(
            f"Configuration file not found: {path}. "
            "Copy config.example.toml and adjust it."
        )

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    app = raw.get("app", {})
    xray = raw.get("xray", {})
    xui_database = raw.get("xui_database", {})
    interval = int(app.get("poll_interval_seconds", 15))
    retention = int(app.get("retention_days", 30))
    port = int(xray.get("api_port", 62789))
    snapshot_max_age = int(xui_database.get("snapshot_max_age_seconds", 180))

    if not 5 <= interval <= 3600:
        raise ValueError("poll_interval_seconds must be between 5 and 3600")
    if not 1 <= retention <= 3650:
        raise ValueError("retention_days must be between 1 and 3650")
    if not 1 <= port <= 65535:
        raise ValueError("xray.api_port must be between 1 and 65535")
    if not 10 <= snapshot_max_age <= 3600:
        raise ValueError("xui_database.snapshot_max_age_seconds must be between 10 and 3600")

    db_path = Path(
        app.get(
            "database_path",
            "/var/lib/xui-intelligence/monitoring.sqlite3",
        )
    )
    if not db_path.is_absolute():
        raise ValueError("database_path must be an absolute path")

    binary = str(xray.get("binary", "/usr/local/x-ui/bin/xray"))
    if not binary.startswith("/"):
        raise ValueError("xray.binary must be an absolute path")

    address = str(xray.get("api_address", "127.0.0.1"))
    if address != "localhost":
        try:
            parsed_address = ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError(
                "xray.api_address must be localhost or a loopback IP"
            ) from exc
        if not parsed_address.is_loopback:
            raise ValueError("xray.api_address must be a loopback IP")

    snapshot_path = Path(
        xui_database.get(
            "snapshot_path",
            "/var/lib/xui-intelligence/xui-readonly.sqlite3",
        )
    )
    if not snapshot_path.is_absolute():
        raise ValueError("xui_database.snapshot_path must be absolute")

    return AppConfig(
        poll_interval_seconds=interval,
        retention_days=retention,
        database_path=db_path,
        xray_enabled=bool(xray.get("enabled", False)),
        xray_binary=binary,
        xray_address=address,
        xray_port=port,
        xui_database_enabled=bool(xui_database.get("enabled", False)),
        xui_snapshot_path=snapshot_path,
        xui_snapshot_max_age_seconds=snapshot_max_age,
    )
