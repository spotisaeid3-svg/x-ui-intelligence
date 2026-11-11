"""Private-chat, allowlisted Telegram reporting. No management commands exist."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from .config import AppConfig

logger = logging.getLogger(__name__)


def latest_snapshot_readonly(database_path: Path) -> dict[str, Any] | None:
    """Read the last stored sample without opening the database for writes."""
    if not database_path.is_file():
        return None
    uri = database_path.as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        connection.execute("PRAGMA query_only=ON")
        row = connection.execute(
            "SELECT captured_at, payload_json FROM snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row[1])
        if not isinstance(payload, dict):
            return None
        return {"captured_at": str(row[0]), "payload": payload}
    except (sqlite3.Error, json.JSONDecodeError, TypeError):
        logger.exception("Could not read the latest monitoring snapshot")
        return None
    finally:
        connection.close()


def _number(value: object, suffix: str = "") -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    return f"{value:.1f}{suffix}"


def _bytes(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return "—"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return "—"


def _aggregate_network_rate(rates: object, field: str) -> float | None:
    if not isinstance(rates, dict):
        return None
    total = 0.0
    seen = False
    for counters in rates.values():
        if isinstance(counters, dict):
            value = counters.get(field)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                total += value
                seen = True
    return total if seen else None


def format_status(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return "هنوز هیچ نمونه‌ای ثبت نشده است. سرویس مانیتورینگ باید حداقل یک چرخه اجرا شود."
    payload = snapshot.get("payload", {})
    cpu = payload.get("cpu", {})
    memory = payload.get("memory", {})
    disk = payload.get("disk_root", {})
    analytics = payload.get("analytics", {})
    xray = payload.get("xray", {})
    xui = payload.get("xui_database", {})
    alerts = analytics.get("alerts", []) if isinstance(analytics, dict) else []
    lines = [
        "X-UI Intelligence | وضعیت مانیتورینگ",
        f"میزبان: {payload.get('hostname', '—')}",
        f"آخرین نمونه (UTC): {snapshot.get('captured_at', '—')}",
        "",
        f"CPU: {_number(cpu.get('usage_percent'), '%')}",
        f"RAM: {_number(memory.get('used_percent'), '%')}  ({_bytes(memory.get('used_bytes'))} / {_bytes(memory.get('total_bytes'))})",
        f"Disk /: {_number(disk.get('used_percent'), '%')}  ({_bytes(disk.get('used_bytes'))} / {_bytes(disk.get('total_bytes'))})",
        f"Uptime: {_number((payload.get('uptime_seconds') or 0) / 86400, ' روز')}",
        f"Xray Stats: {'فعال' if xray.get('available') else 'غیرفعال/بدون داده'}",
    ]
    rx_rate = _aggregate_network_rate(analytics.get("network_bytes_per_second"), "rx_bytes")
    tx_rate = _aggregate_network_rate(analytics.get("network_bytes_per_second"), "tx_bytes")
    if rx_rate is not None or tx_rate is not None:
        lines.append(f"Network rate: دریافت {_bytes(rx_rate)}/s | ارسال {_bytes(tx_rate)}/s")
    xray_rates = analytics.get("xray_bytes_per_second", {})
    if isinstance(xray_rates, dict):
        scope = "user" if any(key.startswith("user_") for key in xray_rates) else "inbound"
        down = xray_rates.get(f"{scope}_downlink_bytes")
        up = xray_rates.get(f"{scope}_uplink_bytes")
        if down is not None or up is not None:
            lines.append(f"Xray rate: دریافت {_bytes(down)}/s | ارسال {_bytes(up)}/s")
    if xui.get("available"):
        counts = xui.get("row_counts", {})
        lines.append(
            "X-UI snapshot: فعال | "
            + " | ".join(f"{key}: {counts.get(key, '—')}" for key in ("clients", "inbounds"))
        )
    else:
        lines.append("X-UI snapshot: غیرفعال/بدون داده")
    lines.append(f"هشدارهای فعلی: {len(alerts) if isinstance(alerts, list) else 0}")
    return "\n".join(lines)[:3500]


def format_alerts(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return "هنوز داده‌ای برای بررسی هشدارها وجود ندارد."
    alerts = snapshot.get("payload", {}).get("analytics", {}).get("alerts", [])
    if not alerts:
        return "در آخرین نمونه، هشدار آستانه‌ای فعالی ثبت نشده است."
    lines = ["هشدارهای آخرین نمونه:"]
    for alert in alerts[:20]:
        if not isinstance(alert, dict):
            continue
        severity = str(alert.get("severity", "unknown")).upper()
        message = str(alert.get("message", "Alert"))[:180]
        lines.append(f"• {severity}: {message}")
    return "\n".join(lines)[:3500]


async def run_telegram_bot(config: AppConfig) -> None:
    """Start allowlisted read-only polling. Import aiogram only when enabled."""
    try:
        from aiogram import Bot, Dispatcher, Router
        from aiogram.filters import Command
    except ImportError as exc:  # pragma: no cover - deployment integration
        raise RuntimeError(
            "Telegram is enabled but the optional 'telegram' dependencies are missing; "
            "reinstall with pip install '.[telegram]'"
        ) from exc

    bot = Bot(token=config.telegram_bot_token)
    dispatcher = Dispatcher()
    router = Router()

    async def authorize(message, command: str) -> bool:
        sender_id = message.from_user.id if message.from_user else 0
        private_chat = message.chat.type == "private"
        allowed = private_chat and sender_id in config.telegram_allowed_user_ids
        if not allowed:
            logger.warning(
                "Rejected Telegram request command=%s sender_id=%s private_chat=%s",
                command,
                sender_id,
                private_chat,
            )
        return allowed

    @router.message(Command("start", "help"))
    async def help_handler(message) -> None:
        if not await authorize(message, "help"):
            return
        await message.answer(
            "X-UI Intelligence — مانیتورینگ فقط‌خواندنی\n\n"
            "/status — وضعیت آخرین نمونه\n"
            "/alerts — هشدارهای آستانه‌ای\n"
            "/help — راهنما\n\n"
            "ربات فقط گزارش می‌دهد؛ هیچ فرمان مدیریتی، اجرای shell یا تغییر تنظیماتی ندارد."
        )

    @router.message(Command("status"))
    async def status_handler(message) -> None:
        if not await authorize(message, "status"):
            return
        snapshot = await asyncio.to_thread(latest_snapshot_readonly, config.database_path)
        await message.answer(format_status(snapshot))

    @router.message(Command("alerts"))
    async def alerts_handler(message) -> None:
        if not await authorize(message, "alerts"):
            return
        snapshot = await asyncio.to_thread(latest_snapshot_readonly, config.database_path)
        await message.answer(format_alerts(snapshot))

    dispatcher.include_router(router)
    logger.info("Telegram reporting enabled for %d allowlisted user(s)", len(config.telegram_allowed_user_ids))
    await dispatcher.start_polling(
        bot,
        allowed_updates=dispatcher.resolve_used_update_types(),
    )
