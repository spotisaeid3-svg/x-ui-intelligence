# X-UI database access design

## Separation of duties

The live database at `/etc/x-ui/x-ui.db` retains its existing owner and
restrictive permissions. The application service never receives direct access.

A fixed-path root-run exporter uses SQLite's online backup API from a read-only
source connection and publishes a consistent copy at:

`/var/lib/xui-intelligence-snapshot/xui-readonly.sqlite3`

The snapshot directory is owned by `root` and the monitoring service's primary
group, with mode `0750`. The snapshot file is owned by `root` and that group,
with mode `0640`. The service can read the file but cannot replace it or write
to its parent directory. Keep the app's writable state directory separate.

The application opens the snapshot with SQLite `mode=ro`,
`PRAGMA query_only=ON`, and `PRAGMA trusted_schema=OFF`.

## Fail-closed behavior

- The exporter accepts no command-line paths or arbitrary SQL.
- It refuses symlinks and non-regular source database paths.
- It never updates, vacuums, checkpoints, or changes journal mode on the live DB.
- It writes to a temporary file, runs `quick_check`, and atomically renames it.
- The collector rejects missing, stale, or invalid snapshots.
- Only aggregate counts from a fixed table allowlist are returned.
- Client UUIDs, email-like identifiers, labels, tokens, and raw row contents are not returned.

## Target VPS validation

The target VPS reported SQLite 3.45.1, journal mode `wal`, and existing
`x-ui.db-wal` / `x-ui.db-shm` sidecars with mode `0600`. A read-only
SQLite Online Backup API test completed successfully and the copied database
passed `PRAGMA quick_check`.

This validates the backup method on the live host. It does not yet validate the
installed helper's ownership, service account group membership, timer behavior,
or production permissions.

## Deployment gate

Before enabling the exporter:

1. Confirm the dedicated `xui-intelligence` account and its primary group.
2. Install the exporter as root-owned and non-writable by the monitoring account.
3. Confirm the snapshot directory is `root:<service-primary-group>` mode `0750`.
4. Confirm the snapshot file is `root:<service-primary-group>` mode `0640`.
5. Run one manual export and test the reader as the unprivileged service account.
6. Only then consider a systemd timer.

Do not change ownership or permissions of the live X-UI database or its WAL/SHM
sidecars. Do not grant generic sudo access to the exporter.
