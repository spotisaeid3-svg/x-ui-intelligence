"""Command-line runner for periodic read-only collection and reporting."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from xui_intelligence.analytics import analyze_snapshots
from xui_intelligence.collectors.system import SystemCollector
from xui_intelligence.collectors.xray import XrayStatsCollector, XrayStatsError
from xui_intelligence.collectors.xui_database import XuiDatabaseCollector, XuiSnapshotError
from xui_intelligence.config import AppConfig, load_config
from xui_intelligence.storage import MonitoringStore

logger = logging.getLogger(__name__)


def collect_and_store(
    config: AppConfig,
    collector: SystemCollector | None,
    xray_collector: XrayStatsCollector | None = None,
    xui_collector: XuiDatabaseCollector | None = None,
) -> dict[str, Any]:
    metrics: dict[str, Any] = collector.collect() if collector is not None else {}
    if xray_collector is not None:
        try:
            metrics["xray"] = xray_collector.collect()
        except XrayStatsError as exc:
            metrics["xray"] = {"available": False, "error": str(exc)}
    if xui_collector is not None:
        try:
            metrics["xui_database"] = xui_collector.collect()
        except XuiSnapshotError as exc:
            metrics["xui_database"] = {"available": False, "error": str(exc)}

    with MonitoringStore(config.database_path) as store:
        previous = store.latest_snapshot()
        elapsed_seconds: float | None = None
        if previous is not None:
            try:
                previous_time = datetime.fromisoformat(previous["captured_at"])
                elapsed_seconds = (
                    datetime.now(previous_time.tzinfo) - previous_time
                ).total_seconds()
            except (TypeError, ValueError):
                elapsed_seconds = None
        metrics["analytics"] = analyze_snapshots(
            previous["payload"] if previous is not None else None,
            metrics,
            elapsed_seconds=elapsed_seconds,
        )
        store.record_snapshot(metrics)
        store.prune(config.retention_days)
    return metrics


def build_collectors(config: AppConfig) -> tuple[SystemCollector | None, XrayStatsCollector | None, XuiDatabaseCollector | None]:
    return (
        SystemCollector() if config.host_enabled else None,
        XrayStatsCollector(
            binary=config.xray_binary,
            address=config.xray_address,
            port=config.xray_port,
        ) if config.xray_enabled else None,
        XuiDatabaseCollector(
            snapshot_path=str(config.xui_snapshot_path),
            max_age_seconds=config.xui_snapshot_max_age_seconds,
        ) if config.xui_database_enabled else None,
    )


async def run_service(config: AppConfig) -> None:
    collector, xray_collector, xui_collector = build_collectors(config)
    telegram_task: asyncio.Task[None] | None = None
    if config.telegram_enabled:
        from xui_intelligence.telegram_bot import run_telegram_bot

        telegram_task = asyncio.create_task(run_telegram_bot(config), name="telegram-reporting")

    logger.info(
        "Starting read-only monitoring interval=%ss xray_enabled=%s xui_db_enabled=%s telegram_enabled=%s",
        config.poll_interval_seconds,
        config.xray_enabled,
        config.xui_database_enabled,
        config.telegram_enabled,
    )
    try:
        while True:
            if telegram_task is not None and telegram_task.done():
                await telegram_task
            try:
                snapshot = await asyncio.to_thread(
                    collect_and_store, config, collector, xray_collector, xui_collector
                )
                logger.info(
                    "Snapshot stored cpu=%s memory=%s disk=%s alerts=%d",
                    snapshot.get("cpu", {}).get("usage_percent"),
                    snapshot.get("memory", {}).get("used_percent"),
                    snapshot.get("disk_root", {}).get("used_percent"),
                    len(snapshot.get("analytics", {}).get("alerts", [])),
                )
            except Exception:
                logger.exception("Monitoring cycle failed")
            await asyncio.sleep(config.poll_interval_seconds)
    finally:
        if telegram_task is not None:
            telegram_task.cancel()
            await asyncio.gather(telegram_task, return_exceptions=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only X-UI Intelligence monitor")
    parser.add_argument(
        "--config", type=Path, default=Path("/etc/xui-intelligence/config.toml")
    )
    parser.add_argument("--once", action="store_true", help="collect one sample and exit")
    parser.add_argument("--check-config", action="store_true", help="validate config without collecting")
    args = parser.parse_args()

    config = load_config(args.config)
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.check_config:
        print("Configuration OK")
        return

    collector, xray_collector, xui_collector = build_collectors(config)
    if args.once:
        print(
            json.dumps(
                collect_and_store(config, collector, xray_collector, xui_collector),
                indent=2,
            )
        )
        return
    try:
        asyncio.run(run_service(config))
    except KeyboardInterrupt:
        logger.info("Monitoring stopped")


if __name__ == "__main__":
    main()
