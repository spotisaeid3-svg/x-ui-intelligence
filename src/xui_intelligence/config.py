"""Validated TOML configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    poll_interval_seconds: int
    retention_days: int
    database_path: Path


def load_config(path: Path) -> AppConfig:
    if not path.is_file():
        raise FileNotFoundError(
            f"Configuration file not found: {path}. "
            "Copy config.example.toml and adjust it."
        )

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    app = raw.get("app", {})
    interval = int(app.get("poll_interval_seconds", 15))
    retention = int(app.get("retention_days", 30))

    if not 5 <= interval <= 3600:
        raise ValueError("poll_interval_seconds must be between 5 and 3600")
    if not 1 <= retention <= 3650:
        raise ValueError("retention_days must be between 1 and 3650")

    db_path = Path(
        app.get(
            "database_path",
            "/var/lib/xui-intelligence/monitoring.sqlite3",
        )
    )
    if not db_path.is_absolute():
        raise ValueError("database_path must be an absolute path")

    return AppConfig(
        poll_interval_seconds=interval,
        retention_days=retention,
        database_path=db_path,
    )
