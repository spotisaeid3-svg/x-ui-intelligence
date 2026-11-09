import os
import sqlite3
import time
from pathlib import Path

import pytest

from xui_intelligence.collectors.xui_database import (
    XuiDatabaseCollector,
    XuiSnapshotError,
)


def make_snapshot(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE clients (id INTEGER PRIMARY KEY, uuid TEXT);
        CREATE TABLE inbounds (id INTEGER PRIMARY KEY, remark TEXT);
        CREATE TABLE client_traffics (id INTEGER PRIMARY KEY);
        INSERT INTO clients(uuid) VALUES ('must-not-leak-this-value');
        INSERT INTO inbounds(remark) VALUES ('private inbound label');
        """
    )
    connection.commit()
    connection.close()


def test_collector_returns_counts_without_private_values(tmp_path: Path) -> None:
    snapshot = tmp_path / "xui.sqlite3"
    make_snapshot(snapshot)

    result = XuiDatabaseCollector(str(snapshot)).collect()

    assert result["row_counts"]["clients"] == 1
    assert result["row_counts"]["inbounds"] == 1
    assert "must-not-leak" not in repr(result)
    assert "private inbound" not in repr(result)


def test_collector_rejects_stale_snapshot(tmp_path: Path) -> None:
    snapshot = tmp_path / "xui.sqlite3"
    make_snapshot(snapshot)
    old = time.time() - 600
    os.utime(snapshot, (old, old))

    with pytest.raises(XuiSnapshotError, match="stale"):
        XuiDatabaseCollector(str(snapshot), max_age_seconds=30).collect()


def test_collector_rejects_missing_snapshot(tmp_path: Path) -> None:
    with pytest.raises(XuiSnapshotError, match="does not exist"):
        XuiDatabaseCollector(str(tmp_path / "missing.sqlite3")).collect()


def test_collector_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "real.sqlite3"
    make_snapshot(target)
    link = tmp_path / "link.sqlite3"
    link.symlink_to(target)

    with pytest.raises(XuiSnapshotError, match="regular file"):
        XuiDatabaseCollector(str(link)).collect()
