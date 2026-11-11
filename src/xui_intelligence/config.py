"""Validated TOML configuration for the read-only monitor."""

from __future__ import annotations

import ipaddress
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    poll_interval_seconds: int
    retention_days: int
    database_path: Path
    log_level: str
    host_enabled: bool
    xray_enabled: bool
    xray_binary: str
    xray_address: str
    xray_port: int
    xui_database_enabled: bool
    xui_snapshot_path: Path
    xui_snapshot_max_age_seconds: int
    telegram_enabled: bool
    telegram_bot_token: str
    telegram_allowed_user_ids: frozenset[int]


def _boolean(section: dict[str, object], key: str, default: bool) -> bool:
    value = section.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a TOML boolean")
    return value


def _positive_ids(value: object) -> frozenset[int]:
    if not isinstance(value, list):
        raise ValueError("telegram.allowed_user_ids must be an array of positive integers")
    result: set[int] = set()
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise ValueError("telegram.allowed_user_ids must contain positive integers only")
        result.add(item)
    return frozenset(result)


def _env_ids(raw: str) -> frozenset[int]:
    values: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if not item.isdecimal() or int(item) <= 0:
            raise ValueError(
                "XUI_INTELLIGENCE_TELEGRAM_ALLOWED_IDS must be comma-separated positive integers"
            )
        values.add(int(item))
    return frozenset(values)


def load_config(path: Path) -> AppConfig:
    if not path.is_file():
        raise FileNotFoundError(
            f"Configuration file not found: {path}. Copy config.example.toml and adjust it."
        )

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    app = raw.get("app", {})
    host = raw.get("host", {})
    xray = raw.get("xray", {})
    xui_database = raw.get("xui_database", {})
    telegram = raw.get("telegram", {})
    sections = {"app": app, "host": host, "xray": xray,
                "xui_database": xui_database, "telegram": telegram}
    for section_name, section in sections.items():
        if not isinstance(section, dict):
            raise ValueError(f"[{section_name}] must be a TOML table")

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

    db_path = Path(app.get("database_path", "/var/lib/xui-intelligence/monitoring.sqlite3"))
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
            raise ValueError("xray.api_address must be localhost or a loopback IP") from exc
        if not parsed_address.is_loopback:
            raise ValueError("xray.api_address must be a loopback IP")

    snapshot_path = Path(
        xui_database.get(
            "snapshot_path", "/var/lib/xui-intelligence-snapshot/xui-readonly.sqlite3"
        )
    )
    if not snapshot_path.is_absolute():
        raise ValueError("xui_database.snapshot_path must be absolute")

    raw_level = str(app.get("log_level", "INFO")).upper()
    if raw_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("app.log_level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")

    host_enabled = _boolean(host, "enabled", True)
    xray_enabled = _boolean(xray, "enabled", False)
    xui_database_enabled = _boolean(xui_database, "enabled", False)
    telegram_enabled = _boolean(telegram, "enabled", False)
    allowed_ids = _positive_ids(telegram.get("allowed_user_ids", []))
    env_ids = os.getenv("XUI_INTELLIGENCE_TELEGRAM_ALLOWED_IDS")
    if env_ids is not None:
        allowed_ids = _env_ids(env_ids)
    token = os.getenv("XUI_INTELLIGENCE_TELEGRAM_BOT_TOKEN", "").strip()
    if telegram_enabled and not token:
        raise ValueError(
            "Telegram is enabled but XUI_INTELLIGENCE_TELEGRAM_BOT_TOKEN is not set"
        )
    if telegram_enabled and not allowed_ids:
        raise ValueError(
            "Telegram is enabled but no authorized IDs are configured; refusing open access"
        )

    return AppConfig(
        poll_interval_seconds=interval,
        retention_days=retention,
        database_path=db_path,
        log_level=raw_level,
        host_enabled=host_enabled,
        xray_enabled=xray_enabled,
        xray_binary=binary,
        xray_address=address,
        xray_port=port,
        xui_database_enabled=xui_database_enabled,
        xui_snapshot_path=snapshot_path,
        xui_snapshot_max_age_seconds=snapshot_max_age,
        telegram_enabled=telegram_enabled,
        telegram_bot_token=token,
        telegram_allowed_user_ids=allowed_ids,
    )
