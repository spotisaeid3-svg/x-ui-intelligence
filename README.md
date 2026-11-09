# X-UI Intelligence

Read-only monitoring and alerting for an X-UI / Xray VPS.

> **V1 safety boundary:** monitoring only. The application does not restart services, modify X-UI/Xray configuration, manage clients, change firewall rules, or execute arbitrary shell commands.

## Implemented

- Linux host telemetry: CPU utilization, memory, root filesystem, load average, uptime, and network counters.
- Independent SQLite history with configurable retention.
- Pure analytics for host-network and aggregate Xray byte rates, counter-reset detection, and configurable CPU/memory/disk threshold alerts.
- Opt-in Xray StatsService collector using `statsquery`, `-reset=false`, a fixed subprocess argument list, and loopback-only API validation.
- Opt-in X-UI database snapshot reader. It returns aggregate counts from a fixed table allowlist and never returns client identifiers or raw rows.
- Fixed-path SQLite snapshot exporter, designed to run separately with elevated privileges and publish a read-only copy for the unprivileged application.
- Unit tests and GitHub Actions test workflow.

## Important deployment limitation

**This repository is not yet an installable release.** The X-UI snapshot exporter must not be installed or enabled until the live database journal mode and WAL/SHM sidecar permissions are checked on the target VPS and a backup test succeeds. The exporter is privileged code and requires a root-owned, non-writable installation.

## Design

- Python application runs as a dedicated unprivileged Linux user.
- Monitoring history is stored in an independent SQLite database.
- The live X-UI database keeps its existing owner and restrictive permissions.
- Xray API access is limited to loopback.
- Telegram integration is not implemented yet; when added, it will be reporting/notification only, with explicit sender authorization and no remote shell.
- Secrets must never be committed to Git.

## Requirements

- Ubuntu 24.04 or compatible Linux
- Python 3.11+
- systemd
- Git

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest -q
xui-intelligence --once
```

## Configuration

Copy `config.example.toml` to `/etc/xui-intelligence/config.toml` and adjust values. Xray and X-UI snapshot collection are disabled by default. Never put API tokens or bot tokens in Git.

## Security

- No arbitrary command execution.
- No write access to the live X-UI database.
- No changes to X-UI, Xray, firewall, or system service state.
- No client UUIDs, tokens, private keys, or raw database rows in monitoring output.
- Logs and reports must mask identifiers and credentials.

## Documentation

- [Security boundary](docs/security-boundary.md)
- [Host telemetry semantics](docs/telemetry.md)
- [Snapshot analytics](docs/analytics.md)
- [X-UI database access design](docs/xui-database-access.md)
- [Deployment notes](docs/deployment-notes.md)

## Roadmap

1. Validate collectors and CI on a clean environment.
2. Validate Xray StatsService behavior on the target VPS.
3. Validate the X-UI snapshot exporter against the live SQLite journal mode and sidecars.
4. Add log parsing and statistical anomaly detection.
5. Add alert persistence, deduplication, and Telegram reporting/notifications.
6. Add a hardened installer and systemd units after operational validation.
