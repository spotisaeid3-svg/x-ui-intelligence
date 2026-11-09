"""Root-run, fixed-path SQLite snapshot exporter for the X-UI database.

This helper has no user-controlled path arguments and never writes to the live
X-UI database. Install it as a root-owned executable only after validating the
live database journal mode and sidecar permissions on the target host.
"""

from __future__ import annotations

import os
import pwd
import shutil
import sqlite3
import stat
import tempfile
from pathlib import Path

SOURCE_DB = Path("/etc/x-ui/x-ui.db")
SNAPSHOT_DIR = Path("/var/lib/xui-intelligence")
SNAPSHOT_DB = SNAPSHOT_DIR / "xui-readonly.sqlite3"
SERVICE_ACCOUNT = "xui-intelligence"


def _require_regular_non_symlink(path: Path) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"Refusing non-regular or symlink database path: {path}")


def create_snapshot() -> dict[str, object]:
    """Create a consistent SQLite backup and atomically publish it to the app."""
    _require_regular_non_symlink(SOURCE_DB)
    account = pwd.getpwnam(SERVICE_ACCOUNT)

    SNAPSHOT_DIR.mkdir(mode=0o750, parents=True, exist_ok=True)
    directory_info = SNAPSHOT_DIR.lstat()
    if stat.S_ISLNK(directory_info.st_mode) or not stat.S_ISDIR(directory_info.st_mode):
        raise RuntimeError("Snapshot directory must be a real directory, not a symlink")

    os.chown(SNAPSHOT_DIR, account.pw_uid, account.pw_gid)
    os.chmod(SNAPSHOT_DIR, 0o750)

    source_uri = SOURCE_DB.as_uri() + "?mode=ro"
    source = sqlite3.connect(source_uri, uri=True, timeout=10)
    temporary_path: Path | None = None
    destination: sqlite3.Connection | None = None

    try:
        source.execute("PRAGMA query_only=ON")
        journal_mode = str(source.execute("PRAGMA journal_mode").fetchone()[0]).lower()

        # SQLite's backup API provides a consistent database image. If the
        # active WAL/SHM sidecars cannot be read, backup fails closed.
        file_descriptor, temp_name = tempfile.mkstemp(
            prefix=".xui-snapshot-",
            suffix=".sqlite3",
            dir=SNAPSHOT_DIR,
        )
        os.close(file_descriptor)
        temporary_path = Path(temp_name)

        destination = sqlite3.connect(temporary_path, timeout=10)
        source.backup(destination)
        check = destination.execute("PRAGMA quick_check").fetchone()
        if not check or check[0] != "ok":
            raise RuntimeError("SQLite snapshot quick_check failed")

        destination.close()
        destination = None

        os.chmod(temporary_path, 0o600)
        os.chown(temporary_path, account.pw_uid, account.pw_gid)
        os.replace(temporary_path, SNAPSHOT_DB)
        temporary_path = None

        return {
            "status": "ok",
            "journal_mode": journal_mode,
            "snapshot_path": str(SNAPSHOT_DB),
            "snapshot_bytes": SNAPSHOT_DB.stat().st_size,
        }
    finally:
        if destination is not None:
            destination.close()
        source.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    print(create_snapshot())
