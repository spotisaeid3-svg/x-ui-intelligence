"""Read-only inventory counts from the exported X-UI SQLite snapshot."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

EXPECTED_TABLES = (
    "clients",
    "inbounds",
    "client_traffics",
    "inbound_client_ips",
)


class XuiSnapshotError(RuntimeError):
    """Raised when the X-UI snapshot is absent, stale, or invalid."""


class XuiDatabaseCollector:
    """Read aggregate inventory counts only; never return client identifiers."""

    def __init__(
        self,
        snapshot_path: str = "/var/lib/xui-intelligence/xui-readonly.sqlite3",
        max_age_seconds: int = 180,
    ) -> None:
        self.snapshot_path = Path(snapshot_path)
        if not self.snapshot_path.is_absolute():
            raise ValueError("X-UI snapshot path must be absolute")
        if not 10 <= max_age_seconds <= 3600:
            raise ValueError("max_age_seconds must be between 10 and 3600")
        self.max_age_seconds = max_age_seconds

    def collect(self) -> dict[str, Any]:
        try:
            info = self.snapshot_path.lstat()
        except FileNotFoundError as exc:
            raise XuiSnapshotError("X-UI snapshot does not exist yet") from exc

        if self.snapshot_path.is_symlink() or not self.snapshot_path.is_file():
            raise XuiSnapshotError("X-UI snapshot path is not a regular file")

        age = max(0.0, time.time() - info.st_mtime)
        if age > self.max_age_seconds:
            raise XuiSnapshotError(
                f"X-UI snapshot is stale ({int(age)} seconds old)"
            )

        uri = self.snapshot_path.as_uri() + "?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=5)
        except sqlite3.Error as exc:
            raise XuiSnapshotError(f"Cannot open X-UI snapshot: {exc}") from exc

        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            check = connection.execute("PRAGMA quick_check").fetchone()
            if not check or check[0] != "ok":
                raise XuiSnapshotError("X-UI snapshot failed SQLite quick_check")

            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }

            counts: dict[str, int] = {}
            for table in EXPECTED_TABLES:
                if table in tables:
                    # Table names come only from this constant allowlist.
                    counts[table] = int(
                        connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                    )

            return {
                "available": True,
                "snapshot_age_seconds": int(age),
                "tables_found": sorted(tables.intersection(EXPECTED_TABLES)),
                "row_counts": counts,
            }
        except sqlite3.Error as exc:
            raise XuiSnapshotError(f"Cannot inspect X-UI snapshot: {exc}") from exc
        finally:
            connection.close()
