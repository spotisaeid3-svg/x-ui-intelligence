import os
import sqlite3
import stat
from pathlib import Path
from types import SimpleNamespace

from xui_intelligence import snapshot_exporter


def test_exporter_publishes_group_read_only_snapshot(tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "source.sqlite3"
    connection = sqlite3.connect(source_path)
    connection.execute("CREATE TABLE clients (id INTEGER PRIMARY KEY)")
    connection.execute("INSERT INTO clients DEFAULT VALUES")
    connection.commit()
    connection.close()

    snapshot_dir = tmp_path / "root-owned-snapshots"
    snapshot_path = snapshot_dir / "xui-readonly.sqlite3"
    chown_calls = []

    monkeypatch.setattr(snapshot_exporter, "SOURCE_DB", source_path)
    monkeypatch.setattr(snapshot_exporter, "SNAPSHOT_DIR", snapshot_dir)
    monkeypatch.setattr(snapshot_exporter, "SNAPSHOT_DB", snapshot_path)
    monkeypatch.setattr(
        snapshot_exporter.pwd,
        "getpwnam",
        lambda _: SimpleNamespace(pw_uid=12345, pw_gid=23456),
    )
    monkeypatch.setattr(
        snapshot_exporter.os,
        "chown",
        lambda path, uid, gid: chown_calls.append((Path(path), uid, gid)),
    )

    result = snapshot_exporter.create_snapshot()

    assert result["status"] == "ok"
    assert result["journal_mode"] in {"delete", "wal"}
    assert stat.S_IMODE(snapshot_dir.stat().st_mode) == 0o750
    assert stat.S_IMODE(snapshot_path.stat().st_mode) == 0o640
    assert (snapshot_dir, 0, 23456) in chown_calls
    assert any(
        path.parent == snapshot_dir
        and path.name.startswith(".xui-snapshot-")
        and uid == 0
        and gid == 23456
        for path, uid, gid in chown_calls
    )

    reader = sqlite3.connect(f"{snapshot_path.as_uri()}?mode=ro", uri=True)
    try:
        assert reader.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 1
    finally:
        reader.close()
