# Deployment notes

This repository is not yet an installable release.

## Current safe scope

- Host telemetry reads procfs and filesystem statistics.
- Xray stats collection is opt-in and restricted to a loopback API address.
- X-UI database analysis is opt-in and reads only a separately exported snapshot.
- The app writes only to its own monitoring database.
- No service-control, panel-management, firewall, or remote-shell features exist.

## Target VPS observations

- Ubuntu 24.04.5 LTS, Python environment to be checked at deployment time.
- X-UI SQLite database reports journal mode `wal`, SQLite 3.45.1.
- The live `-wal` and `-shm` sidecars were present with mode `0600`.
- A read-only Online Backup API test produced a copy that passed `PRAGMA quick_check`.

## Required pre-install checks

1. Confirm the target host's Python version and available disk space.
2. Confirm the Xray binary path and exact StatsService command output.
3. Confirm the dedicated `xui-intelligence` account and its primary group.
4. Install the exporter as root-owned and non-writable by the monitoring account.
5. Confirm the snapshot directory is `root:<service-primary-group>` mode `0750`.
6. Confirm the snapshot file is `root:<service-primary-group>` mode `0640`.
7. Run one manual export and test the reader as the unprivileged service account.
8. Run unit tests and review GitHub Actions results before creating a release.

The WAL backup method is validated on the target VPS, but the installed helper,
production ownership, service-account read access, and timer behavior are not
yet validated. Do not install or enable the exporter or its timer yet.
