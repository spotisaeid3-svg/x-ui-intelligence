"""Command-line runner for periodic read-only collection."""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

from xui_intelligence.config import AppConfig, load_config
from xui_intelligence.collectors.system import SystemCollector
from xui_intelligence.collectors.xray import XrayStatsCollector, XrayStatsError
from xui_intelligence.storage import MonitoringStore


def collect_and_store(
    config: AppConfig,
    collector: SystemCollector,
    xray_collector: XrayStatsCollector | None = None,
) -> dict[str, Any]:
    metrics = collector.collect()
    if xray_collector is not None:
        try:
            metrics["xray"] = xray_collector.collect()
        except XrayStatsError as exc:
            metrics["xray"] = {"available": False, "error": str(exc)}

    with MonitoringStore(config.database_path) as store:
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

    if args.once:
        print(json.dumps(collect_and_store(config, collector, xray_collector), indent=2))
        return

    logging.info(
        "Starting read-only monitoring; interval=%ss xray_enabled=%s",
        config.poll_interval_seconds,
        config.xray_enabled,
    )
    while True:
        try:
            snapshot = collect_and_store(config, collector, xray_collector)
            logging.info(
                "Snapshot stored: cpu=%s%% memory=%s%% disk=%s%% xray=%s",
                snapshot["cpu"]["usage_percent"],
                snapshot["memory"]["used_percent"],
                snapshot["disk_root"]["used_percent"],
                snapshot.get("xray", {}).get("available", False),
            )
        except Exception:
            logging.exception("Monitoring cycle failed")
        time.sleep(config.poll_interval_seconds)


if __name__ == "__main__":
    main()
