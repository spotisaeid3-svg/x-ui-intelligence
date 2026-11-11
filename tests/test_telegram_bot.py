import json
import sqlite3
from pathlib import Path

from xui_intelligence.telegram_bot import format_alerts, format_status, latest_snapshot_readonly


def test_status_formatter_does_not_include_identifiers() -> None:
    snapshot = {
        "captured_at": "2026-11-12T12:00:00Z",
        "payload": {
            "hostname": "monitor-host",
            "cpu": {"usage_percent": 15.2},
            "memory": {"used_percent": 42.0, "used_bytes": 420, "total_bytes": 1000},
            "disk_root": {"used_percent": 54.0, "used_bytes": 540, "total_bytes": 1000},
            "uptime_seconds": 86400,
            "xray": {"available": True},
            "xui_database": {"available": True, "row_counts": {"clients": 8, "inbounds": 2}},
            "private_uuid": "must-not-be-formatted",
            "analytics": {"alerts": []},
        },
    }
    result = format_status(snapshot)
    assert "monitor-host" in result
    assert "clients: 8" in result
    assert "must-not-be-formatted" not in result


def test_alert_formatter_handles_empty_and_populated_alerts() -> None:
    assert "هشدار" in format_alerts({"payload": {"analytics": {"alerts": []}}})
    result = format_alerts({"payload": {"analytics": {"alerts": [
        {"severity": "critical", "message": "cpu usage is 98%"}
    ]}}})
    assert "CRITICAL" in result
    assert "cpu usage" in result


def test_latest_snapshot_reader_uses_read_only_database(tmp_path: Path) -> None:
    db_path = tmp_path / "monitor.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE snapshots (id INTEGER PRIMARY KEY, captured_at TEXT, payload_json TEXT)"
    )
    conn.execute(
        "INSERT INTO snapshots(captured_at, payload_json) VALUES (?, ?)",
        ("2026-11-12T12:00:00Z", json.dumps({"cpu": {"usage_percent": 10}})),
    )
    conn.commit()
    conn.close()
    result = latest_snapshot_readonly(db_path)
    assert result is not None
    assert result["payload"]["cpu"]["usage_percent"] == 10


def test_latest_snapshot_reader_handles_missing_database(tmp_path: Path) -> None:
    assert latest_snapshot_readonly(tmp_path / "missing.sqlite3") is None


def test_status_includes_aggregate_network_rates() -> None:
    snapshot = {
        "captured_at": "2026-11-12T12:00:00Z",
        "payload": {
            "hostname": "host",
            "cpu": {}, "memory": {}, "disk_root": {}, "uptime_seconds": 1,
            "xray": {"available": True}, "xui_database": {"available": False},
            "analytics": {
                "alerts": [],
                "network_bytes_per_second": {"eth0": {"rx_bytes": 2048, "tx_bytes": 1024}},
                "xray_bytes_per_second": {"user_downlink_bytes": 4096, "user_uplink_bytes": 512},
            },
        },
    }
    result = format_status(snapshot)
    assert "Network rate" in result
    assert "Xray rate" in result
