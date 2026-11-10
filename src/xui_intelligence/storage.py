"""Independent SQLite storage for host monitoring snapshots."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Self


class MonitoringStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: sqlite3.Connection | None = None

    def __enter__(self) -> Self:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=10)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute("PRAGMA busy_timeout=10000")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT NOT NULL
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                payload_json TEXT NOT NULL
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_captured_at "
            "ON snapshots(captured_at)"
        )
        self.connection.commit()
        return self

    def latest_snapshot(self) -> dict[str, Any] | None:
        """Return the newest stored snapshot and its UTC capture timestamp."""
        if self.connection is None:
            raise RuntimeError("MonitoringStore must be used as a context manager")
        row = self.connection.execute(
            "SELECT captured_at, payload_json FROM snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return {"captured_at": row[0], "payload": json.loads(row[1])}

    def record_snapshot(self, payload: dict[str, Any]) -> None:
        if self.connection is None:
            raise RuntimeError("MonitoringStore must be used as a context manager")

        serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        self.connection.execute(
            "INSERT INTO snapshots(payload_json) VALUES (?)",
            (serialized,),
        )
        self.connection.commit()

    def prune(self, retention_days: int) -> int:
        if self.connection is None:
            raise RuntimeError("MonitoringStore must be used as a context manager")
        cursor = self.connection.execute(
            """
            DELETE FROM snapshots
            WHERE captured_at < strftime(
                '%Y-%m-%dT%H:%M:%fZ', 'now', ?
            )
            """,
            (f"-{retention_days} days",),
        )
        self.connection.commit()
        return max(cursor.rowcount, 0)

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
