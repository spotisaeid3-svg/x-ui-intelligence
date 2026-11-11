# X-UI database access design

## Separation of duties

The live database at `/etc/x-ui/x-ui.db` retains its existing owner and restrictive permissions. The unprivileged monitoring service never opens it directly and receives no sudo access.

A fixed-path, root-run exporter opens the source with SQLite `mode=ro`, copies it through the Online Backup API, validates the copy using `PRAGMA quick_check`, converts the snapshot to a self-contained DELETE-journal file, and atomically publishes:

`/var/lib/xui-intelligence-snapshot/xui-readonly.sqlite3`

The directory is owned by `root:xui-intelligence` mode `0750`; the snapshot file is `root:xui-intelligence` mode `0640`. The app's independent writable state directory remains separate.

## Fail-closed behavior

- No command-line paths, arbitrary SQL, or user-controlled source path are accepted.
- The exporter rejects a symlink or non-regular source path.
- The live database is never updated, vacuumed, checkpointed, or switched to another journal mode.
- The exporter writes a temporary copy, checks it, and publishes atomically.
- The collector rejects a missing, stale, symlinked, or invalid snapshot.
- The collector returns aggregate counts only from a fixed table allowlist.
- UUIDs, email-like identifiers, labels, tokens, and raw row contents are not returned.

## Enabling the optional timer

The default installation does not enable the snapshot exporter. Use `sudo ./install.sh --with-xui-snapshot` only after validating live SQLite behavior on the target VPS. The installer runs one backup first; if that fails, it does not enable the timer.

The timer runs the isolated `xui-intelligence-snapshot.service` oneshot service at a one-minute cadence. The service has no network access and can write only to the snapshot directory. It is separate from the main unprivileged collector.

Never broaden permissions on `/etc/x-ui/x-ui.db` or its `-wal` / `-shm` files. Never grant generic sudo rights to the monitoring account.
