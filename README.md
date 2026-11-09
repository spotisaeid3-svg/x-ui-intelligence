# X-UI Intelligence

Read-only monitoring and alerting for an X-UI / Xray VPS.

> **V1 safety boundary:** this project is monitoring-only. It does not restart services, modify X-UI/Xray configuration, manage clients, change firewall rules, or execute arbitrary shell commands.

## Status

Initial project scaffold. The first implementation milestone is host telemetry and durable local history. Xray API and X-UI database collectors will be added behind read-only interfaces after their access paths are validated against the target VPS.

## Design

- Python application, running as a dedicated unprivileged Linux user.
- Independent SQLite database for monitoring history.
- Read-only access to host metrics and, in later milestones, Xray StatsService and the X-UI SQLite database.
- Telegram is a notification/reporting interface only; no remote shell or mutating commands.
- Secrets are supplied through a local environment file and must never be committed.

## Requirements

- Ubuntu 24.04 or compatible Linux
- Python 3.11+
- systemd
- Git

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
xui-intelligence --once
```

## Installation

The installer is intentionally not enabled in this scaffold. It will be added after the collectors and permissions model are validated on the target host. Do not run an unreviewed installer as root.

## Configuration

Copy `config.example.toml` to `/etc/xui-intelligence/config.toml` and adjust the values. Never put API tokens or bot tokens in Git.

## Security

- No arbitrary command execution.
- No write access to the X-UI database.
- No changes to X-UI, Xray, firewall, or system service state.
- Telegram user authorization will be enforced before any private monitoring data is returned.
- Logs and reports must mask UUIDs, tokens, and other credentials.

## Roadmap

1. Host telemetry and SQLite history.
2. Xray API read-only statistics.
3. Safe X-UI database inventory snapshots.
4. Log parsing, anomaly detection, and alert rules.
5. Telegram reporting and notifications.
6. Installer, systemd hardening, and operational validation.
