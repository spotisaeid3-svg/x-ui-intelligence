# Security boundary

## Allowed in 1.0.0

- Read Linux host counters and filesystem statistics.
- Write snapshots and retention cleanup only in the application's independent data directory.
- Query Xray StatsService only when explicitly enabled, using a fixed CLI invocation and a loopback API endpoint. The CLI call uses `-reset=false`.
- Read an optional, separately exported X-UI SQLite snapshot in read-only mode and return aggregate counts from a fixed table allowlist.
- Send read-only reports through Telegram to allowlisted numeric user IDs in private chats.

## Explicitly prohibited / out of scope

- Create, edit, enable, disable, or delete clients, UUIDs, inbounds, or panel settings.
- Change X-UI/Xray configuration, routing, service state, firewall, SSH, or operating-system settings.
- Stop, start, or restart X-UI or Xray.
- Execute shell commands supplied by Telegram or by a remote user.
- Expose raw X-UI rows, UUIDs, email-like identifiers, client labels, credentials, private keys, or decrypted application payloads.
- Bind the Xray API collector to a non-loopback address.

## Telegram controls

- Only private chats are accepted.
- Sender IDs must match the configured numeric allowlist.
- Missing token or allowlist causes startup validation to fail when Telegram is enabled.
- The only commands are `/status`, `/alerts`, and `/help`.
- The bot token is read from `XUI_INTELLIGENCE_TELEGRAM_BOT_TOKEN`; never commit it.
- Store the EnvironmentFile as `root:xui-intelligence` mode `0640`.

## Process and filesystem controls

- The main service runs as dedicated unprivileged user `xui-intelligence`.
- The application code and virtual environment are root-owned and not writable by the service.
- systemd uses `NoNewPrivileges`, an empty capability set, strict filesystem protection, private temporary/device namespaces, and a narrow writable application-state directory.
- The application never receives sudo access.
- The snapshot exporter is a separate fixed-path oneshot systemd service. It is root-run only to read the protected live database and publish a protected snapshot; its paths and SQL behavior are not user-configurable.

## X-UI database handling

The live panel database and WAL/SHM sidecars retain their existing owner and permissions. The exporter opens the live database with SQLite `mode=ro`, calls the Online Backup API, validates the copy, and publishes it atomically. The monitoring process opens only the copied database with `mode=ro`, `query_only=ON`, and `trusted_schema=OFF`.
