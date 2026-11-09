# Deployment notes

This repository is not yet an installable release.

## Current safe scope

- Host telemetry reads procfs and filesystem statistics.
- Xray stats collection is opt-in and restricted to a loopback API address.
- X-UI database analysis is opt-in and reads only a separately exported snapshot.
- The app writes only to its own monitoring database.
- No service-control, panel-management, firewall, or remote-shell features exist.

## Required pre-install checks

1. Confirm the target host's Python version and available disk space.
2. Confirm the Xray binary path and exact StatsService command output.
3. Inspect SQLite journal mode and sidecar files on the live X-UI database.
4. Test the snapshot exporter on a separate copy before touching the live DB.
5. Confirm the dedicated service account and restrictive ownership of all runtime files.
6. Run unit tests and review GitHub Actions results before creating a release.

Do not enable the X-UI snapshot exporter until its behavior has been validated
against the actual journal mode and filesystem permissions on the VPS.
