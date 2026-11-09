import json
from pathlib import Path

from xui_intelligence.storage import MonitoringStore


def test_record_snapshot(tmp_path: Path) -> None:
    database = tmp_path / "data" / "monitor.sqlite3"

    with MonitoringStore(database) as store:
        store.record_snapshot({"cpu": {"usage_percent": 12.5}})
        assert store.connection is not None
        row = store.connection.execute(
            "SELECT payload_json FROM snapshots"
        ).fetchone()

    assert row is not None
    assert json.loads(row[0]) == {"cpu": {"usage_percent": 12.5}}
    assert database.exists()


def test_latest_snapshot_returns_payload_and_capture_time(tmp_path: Path) -> None:
    database = tmp_path / "monitor.sqlite3"

    with MonitoringStore(database) as store:
        assert store.latest_snapshot() is None
        store.record_snapshot({"sample": 1})
        first = store.latest_snapshot()
        store.record_snapshot({"sample": 2})
        latest = store.latest_snapshot()

    assert first is not None
    assert first["payload"] == {"sample": 1}
    assert first["captured_at"].endswith("Z")
    assert latest is not None
    assert latest["payload"] == {"sample": 2}
