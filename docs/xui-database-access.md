# X-UI database access design

## Separation of duties

The live X-UI database is expected at `/etc/x-ui/x-ui.db` and must retain its
existing owner and restrictive permissions. The application service must never
receive direct access to that file.

A narrowly scoped, fixed-path snapshot exporter runs separately with the
privileges needed to read the live database. It uses SQLite's online backup API
from a read-only source connection and publishes a consistent copy at:

`/var/lib/xui-intelligence/xui-readonly.sqlite3`

The snapshot is owned by the dedicated `xui-intelligence` service account and
has mode `0600`. The application opens it with SQLite `mode=ro` and
`PRAGMA query_only=ON`.

## Fail-closed behavior

- The exporter accepts no command-line paths or arbitrary SQL.
- It refuses symlinks and non-regular database paths.
- It never updates, vacuums, checkpoints, or changes journal mode on the live DB.
- The snapshot is written to a temporary file, checked, and atomically renamed.
- The collector rejects missing, stale, or invalid snapshots.
- Only aggregate row counts from a fixed table allowlist are returned.
- Client UUIDs, email-like identifiers, labels, tokens, and raw row contents are not returned.

## Deployment gate

Do not install or enable the exporter until these facts are confirmed on the
actual VPS:

1. Live database journal mode.
2. Presence and permissions of `x-ui.db-wal` and `x-ui.db-shm`, if any.
3. The exact X-UI service account and database access behavior.
4. Successful online backup test on a separate copy.

SQLite read-only WAL access may require readable WAL/SHM sidecars and compatible
directory permissions. If the live DB cannot be read safely without changing
its permissions, deployment must stop and use a different approved snapshot
mechanism.

The exporter is a privileged helper and must be installed root-owned and
non-writable by the monitoring account. It must not be exposed as a generic
sudo command. The snapshot timer is not enabled by this code change.
