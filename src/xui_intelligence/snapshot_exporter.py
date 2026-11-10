"""Root-run, fixed-path SQLite snapshot exporter for the X-UI database.

The live database is opened read-only. The published snapshot is root-owned
and group-readable by the monitoring service, but not writable by that service.
"""

from __future__ import annotations

import os
import pwd
import sqlite3
import stat
import tempfile
from pathlib import Path

SOURCE_DB = Path("/etc/x-ui/x-ui.db")
SNAPSHOT_DIR = Path("/var/lib/xui-intelligence-snapshot")
SNAPSHOT_DB = SNAPSHOT_DIR / "xui-readonly.sqlite3"
SERVICE_ACCOUNT = "xui-intelligence"


def _require_regular_non_symlink(path: Path) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"Refusing non-regular or symlink database path: {path}")


def create_snapshot() -> dict[str, object]:
    """Create a consistent backup and publish it read-only to the app group."""
    _require_regular_non_symlink(SOURCE_DB)
    account = pwd.getpwnam(SERVICE_ACCOUNT)

    # Keep this directory outside the app-writable state directory. The app
    # must not be able to replace either the snapshot or its parent directory.
    SNAPSHOT_DIR.mkdir(mode=0o750, parents=True, exist_ok=True)
    directory_info = SNAPSHOT_DIR.lstat()
    if stat.S_ISLNK(directory_info.st_mode) or not stat.S_ISDIR(directory_info.st_mode):
        raise RuntimeError("Snapshot directory must be a real directory, not a symlink")

    os.chown(SNAPSHOT_DIR, 0, account.pw_gid)
    os.chmod(SNAPSHOT_DIR, 0o750)

    source_uri = SOURCE_DB.as_uri() + "?mode=ro"
    source = sqlite3.connect(source_uri, uri=True, timeout=10)
    temporary_path: Path | None = None
    destination: sqlite3.Connection | None = None

    try:
        source.execute("PRAGMA query_only=ON")
        journal_mode = str(source.execute("PRAGMA journal_mode").fetchone()[0]).lower()

        file_descriptor, temp_name = tempfile.mkstemp(
            prefix=".xui-snapshot-",
            suffix=".sqlite3",
            dir=SNAPSHOT_DIR,
        )
        os.close(file_descriptor)
        temporary_path = Path(temp_name)

        destination = sqlite3.connect(temporary_path, timeout=10)
        source.backup(destination)

        # Publish a self-contained rollback-journal snapshot. A read-only
        # SQLite connection cannot create WAL/SHM sidecars in the protected
        # snapshot directory, so leaving the backup in WAL mode would make
        # read-only consumers fail even though the main database is valid.
        snapshot_journal_mode = str(
            destination.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
        ).lower()
        if snapshot_journal_mode != "delete":
            raise RuntimeError(
                f"Could not convert snapshot to DELETE journal mode: "
                f"{snapshot_journal_mode}"
            )

        check = destination.execute("PRAGMA quick_check").fetchone()
        if not check or check[0] != "ok":
            raise RuntimeError("SQLite snapshot quick_check failed")

        destination.close()
        destination = None

        # Root owns the file; the service's primary group can only read it.
        os.chown(temporary_path, 0, account.pw_gid)
        os.chmod(temporary_path, 0o640)
        os.replace(temporary_path, SNAPSHOT_DB)
        temporary_path = None

        return {
            "status": "ok",
            "journal_mode": journal_mode,
            "snapshot_journal_mode": snapshot_journal_mode,
            "snapshot_path": str(SNAPSHOT_DB),
            "snapshot_bytes": SNAPSHOT_DB.stat().st_size,
            "snapshot_mode": oct(stat.S_IMODE(SNAPSHOT_DB.stat().st_mode)),
        }
    finally:
        if destination is not None:
            destination.close()
        source.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    print(create_snapshot())
