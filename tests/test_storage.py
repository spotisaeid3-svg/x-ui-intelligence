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
