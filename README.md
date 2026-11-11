# X-UI Intelligence 1.0.0

Read-only monitoring and reporting for an X-UI / Xray Linux server.

> **Safety boundary:** this application monitors and reports only. It does not create, edit, enable, disable, or delete X-UI clients or inbounds; change X-UI/Xray configuration; restart or stop services; modify firewall or SSH settings; execute remote shell commands; or inspect decrypted user traffic.

## Included in 1.0.0

- Linux host telemetry: CPU utilization, RAM, root filesystem usage, load average, uptime, and per-interface network counters.
- Independent SQLite snapshot history with configurable retention; the application writes only to its own database.
- Network and aggregate Xray byte-rate calculations, counter-reset detection, and CPU/RAM/disk threshold alerts.
- Optional Xray StatsService collector. It uses a fixed subprocess argument list, `shell=False`, `-reset=false`, and a loopback-only API address.
- Optional X-UI inventory counts from a separate SQLite snapshot. Only aggregate row counts are returned; raw rows, UUIDs, emails, labels, and client details are not exposed.
- Optional Telegram reporting with private-chat enforcement and a numeric sender-ID allowlist. Supported commands are `/status`, `/alerts`, and `/help` only.
- Hardened, unprivileged systemd service; reproducible installer; opt-in root-owned snapshot exporter and timer; safe uninstall that preserves configuration and data.
- Unit tests and GitHub Actions CI.

## Requirements

- Ubuntu 22.04+ or a compatible systemd-based Linux distribution.
- Python 3.11+, `python3-venv`, and `pip`.
- Root access for installation and systemd unit management.
- Outbound HTTPS to the Python package index is required during installation; at runtime, outbound HTTPS is needed only when Telegram polling is enabled.

The installer does not install or modify X-UI/Xray. It installs the monitor's Python dependencies into an isolated virtual environment.

## Install

Clone or download this repository, then run:

```bash
cd x-ui-intelligence
sudo ./install.sh
```

The installer creates a dedicated `xui-intelligence` system user/group, installs the app under `/opt/xui-intelligence`, creates `/etc/xui-intelligence/config.toml` and `/etc/xui-intelligence/xui-intelligence.env`, and enables **only** `xui-intelligence.service`.

Check the service:

```bash
sudo systemctl status xui-intelligence
sudo journalctl -u xui-intelligence -n 100 --no-pager
sudo /opt/xui-intelligence/venv/bin/xui-intelligence \
  --config /etc/xui-intelligence/config.toml --check-config
```

The installer is idempotent for application/configuration files: an existing TOML configuration and environment file are kept. Review the files before enabling optional collectors.

## Enable Telegram reporting

1. Create a bot using Telegram's official BotFather and keep the token private.
2. Put the token and your numeric Telegram user ID in `/etc/xui-intelligence/xui-intelligence.env`:

```ini
XUI_INTELLIGENCE_TELEGRAM_BOT_TOKEN=replace_with_real_token
XUI_INTELLIGENCE_TELEGRAM_ALLOWED_IDS=123456789
```

3. In `/etc/xui-intelligence/config.toml`, set:

```toml
[telegram]
enabled = true
allowed_user_ids = []
```

The environment allowlist overrides the TOML list when present. The service refuses to start Telegram polling if the token or allowlist is missing. The environment file is installed as `root:xui-intelligence` mode `0640`; do not loosen its permissions or commit its content.

4. Restart the monitor:

```bash
sudo systemctl restart xui-intelligence
sudo journalctl -u xui-intelligence -f
```

Only allowlisted users in private chats receive reports. Group chats and unauthorized senders are ignored and logged. The bot has no shell, panel-management, or service-control handlers.

## Enable optional Xray statistics

First verify the actual Xray binary path and that StatsService is configured on a loopback address. Then set the `[xray]` section in `config.toml`:

```toml
[xray]
enabled = true
binary = "/usr/local/x-ui/bin/xray"
api_address = "127.0.0.1"
api_port = 62789
```

The API address must be loopback. The collector calls `statsquery` with `-reset=false`; it does not reset counters. It stores only aggregate traffic counters by scope/direction, not client identifiers. If the binary path or StatsService configuration differs on your VPS, adjust it only after verification.

## Enable optional X-UI inventory snapshots

The application never opens the live X-UI database. A separate, fixed-path root-run helper reads `/etc/x-ui/x-ui.db` read-only using SQLite's online backup API and publishes a protected copy. The monitor can then read aggregate counts from that copy.

Use this option only after validating the target VPS's SQLite journal mode, WAL/SHM sidecars, ownership, and backup behavior:

```bash
sudo ./install.sh --with-xui-snapshot
```

This optional flag performs one snapshot backup before enabling a dedicated systemd timer. It does **not** change the live database, its owner/mode, or its WAL/SHM files. It creates `xui-intelligence-snapshot.service` and `.timer`; it does not grant the monitoring user sudo or root privileges.

Then enable the reader in `/etc/xui-intelligence/config.toml`:

```toml
[xui_database]
enabled = true
snapshot_path = "/var/lib/xui-intelligence-snapshot/xui-readonly.sqlite3"
snapshot_max_age_seconds = 180
```

Restart the monitor and verify the snapshot timer:

```bash
sudo systemctl status xui-intelligence-snapshot.timer
sudo journalctl -u xui-intelligence-snapshot.service -n 50 --no-pager
sudo systemctl restart xui-intelligence
```

If the initial backup fails, installation exits without enabling the snapshot timer. Diagnose the read-only backup issue before retrying; do not broaden permissions on `/etc/x-ui/x-ui.db` or its sidecars.

## Configuration and data locations

| Path | Purpose |
|---|---|
| `/etc/xui-intelligence/config.toml` | Monitoring configuration |
| `/etc/xui-intelligence/xui-intelligence.env` | Runtime Telegram secrets / ID override |
| `/var/lib/xui-intelligence/monitoring.sqlite3` | Application-owned monitoring history |
| `/var/lib/xui-intelligence-snapshot/xui-readonly.sqlite3` | Optional protected X-UI snapshot |
| `/opt/xui-intelligence` | Root-owned application and virtual environment |

Default collection is host-only. Xray, X-UI snapshot reads, and Telegram are opt-in.

## Operations

```bash
sudo systemctl status xui-intelligence
sudo systemctl restart xui-intelligence
sudo journalctl -u xui-intelligence -f
sudo systemctl status xui-intelligence-snapshot.timer
```

To uninstall the application and its systemd units:

```bash
sudo ./uninstall.sh
```

Uninstall preserves `/etc/xui-intelligence`, `/var/lib/xui-intelligence`, and the service account/group. It does not touch X-UI or Xray services. Remove retained data or the service account manually only after reviewing what else uses them.

## Development and tests

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev,telegram]"
ruff check .
pytest -q
bash -n install.sh uninstall.sh
```

See [security boundary](docs/security-boundary.md), [deployment notes](docs/deployment-notes.md), and [X-UI database access](docs/xui-database-access.md).
