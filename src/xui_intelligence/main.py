"""Command-line runner for periodic read-only collection."""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from xui_intelligence.analytics import analyze_snapshots
from xui_intelligence.collectors.system import SystemCollector
from xui_intelligence.collectors.xray import XrayStatsCollector, XrayStatsError
from xui_intelligence.collectors.xui_database import (
    XuiDatabaseCollector,
    XuiSnapshotError,
)
from xui_intelligence.config import AppConfig, load_config
from xui_intelligence.storage import MonitoringStore

logger = logging.getLogger(__name__)


def collect_and_store(
    config: AppConfig,
    collector: SystemCollector,
    xray_collector: XrayStatsCollector | None = None,
    xui_collector: XuiDatabaseCollector | None = None,
) -> dict[str, Any]:
    metrics = collector.collect()
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
                previous_time = datetime.fromisoformat(
                    previous["captured_at"]
                )
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only X-UI Intelligence host monitor"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("/etc/xui-intelligence/config.toml"),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="collect one host snapshot and exit",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    collector = SystemCollector()
    xray_collector = (
        XrayStatsCollector(
            binary=config.xray_binary,
            address=config.xray_address,
            port=config.xray_port,
        )
        if config.xray_enabled
        else None
    )
    xui_collector = (
        XuiDatabaseCollector(
            snapshot_path=str(config.xui_snapshot_path),
            max_age_seconds=config.xui_snapshot_max_age_seconds,
        )
        if config.xui_database_enabled
        else None
    )

    if args.once:
        print(
            json.dumps(
                collect_and_store(config, collector, xray_collector, xui_collector),
                indent=2,
            )
        )
        return

    logger.info(
        "Starting read-only monitoring; interval=%ss xray_enabled=%s xui_db_enabled=%s",
        config.poll_interval_seconds,
        config.xray_enabled,
        config.xui_database_enabled,
    )
    while True:
        try:
            snapshot = collect_and_store(
                config,
                collector,
                xray_collector,
                xui_collector,
            )
            logger.info(
                "Snapshot stored: cpu=%s%% memory=%s%% disk=%s%% xray=%s xui_db=%s",
                snapshot["cpu"]["usage_percent"],
                snapshot["memory"]["used_percent"],
                snapshot["disk_root"]["used_percent"],
                snapshot.get("xray", {}).get("available", False),
                snapshot.get("xui_database", {}).get("available", False),
            )
        except Exception:
            logger.exception("Monitoring cycle failed")
        time.sleep(config.poll_interval_seconds)


if __name__ == "__main__":
    main()
