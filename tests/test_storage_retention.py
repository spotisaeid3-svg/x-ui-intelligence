from pathlib import Path

from xui_intelligence.storage import MonitoringStore


def test_prune_removes_expired_snapshots(tmp_path: Path) -> None:
    database = tmp_path / "monitor.sqlite3"

    with MonitoringStore(database) as store:
        assert store.connection is not None
        store.connection.execute(
            "INSERT INTO snapshots(captured_at, payload_json) "
            "VALUES ('2000-01-01T00:00:00.000Z', '{}')"
        )
        store.connection.commit()
        store.record_snapshot({"fresh": True})

        removed = store.prune(30)
        remaining = store.connection.execute(
            "SELECT COUNT(*) FROM snapshots"
        ).fetchone()[0]

    assert removed == 1
    assert remaining == 1
