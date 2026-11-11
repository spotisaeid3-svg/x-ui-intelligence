#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/opt/xui-intelligence"
CONFIG_DIR="/etc/xui-intelligence"
STATE_DIR="/var/lib/xui-intelligence"
SERVICE_USER="xui-intelligence"
WITH_XUI_SNAPSHOT=0

usage() {
  cat <<'EOF'
Usage: sudo ./install.sh [--with-xui-snapshot]

Default: install and start the unprivileged host/Xray monitor service.
Optional: --with-xui-snapshot also performs one root-run read-only backup of
          /etc/x-ui/x-ui.db and enables the dedicated snapshot refresh timer.
          Use only after confirming the target VPS SQLite/WAL backup behavior.
EOF
}

while (($#)); do
  case "$1" in
    --with-xui-snapshot) WITH_XUI_SNAPSHOT=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./install.sh" >&2
  exit 1
fi
if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemd/systemctl is required." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11+ is required." >&2
  exit 1
fi
python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required")
PY

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for required in pyproject.toml README.md config.example.toml src/xui_intelligence systemd/xui-intelligence.service; do
  [[ -e "${SCRIPT_DIR}/${required}" ]] || { echo "Missing package file: ${required}" >&2; exit 1; }
done

if ! getent group "${SERVICE_USER}" >/dev/null; then
  groupadd --system "${SERVICE_USER}"
fi
if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --gid "${SERVICE_USER}" --home-dir /nonexistent \
    --shell /usr/sbin/nologin --no-create-home "${SERVICE_USER}"
fi
if [[ "$(id -gn "${SERVICE_USER}")" != "${SERVICE_USER}" ]]; then
  echo "Existing ${SERVICE_USER} account must use its matching primary group." >&2
  exit 1
fi

install -d -o root -g root -m 0755 "${APP_DIR}"
install -d -o root -g "${SERVICE_USER}" -m 0750 "${CONFIG_DIR}" "${STATE_DIR}"
rm -rf "${APP_DIR}/src"
install -d -o root -g root -m 0755 "${APP_DIR}/src"
cp -a "${SCRIPT_DIR}/src/xui_intelligence" "${APP_DIR}/src/"
install -m 0644 -o root -g root "${SCRIPT_DIR}/pyproject.toml" "${APP_DIR}/pyproject.toml"
install -m 0644 -o root -g root "${SCRIPT_DIR}/README.md" "${APP_DIR}/README.md"
chown -R root:root "${APP_DIR}"
find "${APP_DIR}" -type d -exec chmod 0755 {} +
find "${APP_DIR}" -type f -exec chmod 0644 {} +

if [[ ! -x "${APP_DIR}/venv/bin/python" ]]; then
  python3 -m venv "${APP_DIR}/venv"
fi
"${APP_DIR}/venv/bin/python" -m pip install --disable-pip-version-check "${APP_DIR}[telegram]"

if [[ ! -f "${CONFIG_DIR}/config.toml" ]]; then
  install -m 0640 -o root -g "${SERVICE_USER}" \
    "${SCRIPT_DIR}/config.example.toml" "${CONFIG_DIR}/config.toml"
else
  chown root:"${SERVICE_USER}" "${CONFIG_DIR}/config.toml"
  chmod 0640 "${CONFIG_DIR}/config.toml"
fi
if [[ ! -f "${CONFIG_DIR}/xui-intelligence.env" ]]; then
  install -m 0640 -o root -g "${SERVICE_USER}" /dev/null \
    "${CONFIG_DIR}/xui-intelligence.env"
else
  chown root:"${SERVICE_USER}" "${CONFIG_DIR}/xui-intelligence.env"
  chmod 0640 "${CONFIG_DIR}/xui-intelligence.env"
fi

install -m 0644 -o root -g root "${SCRIPT_DIR}/systemd/xui-intelligence.service" \
  /etc/systemd/system/xui-intelligence.service

if ((WITH_XUI_SNAPSHOT)); then
  [[ -f /etc/x-ui/x-ui.db && ! -L /etc/x-ui/x-ui.db ]] || {
    echo "Refusing snapshot setup: /etc/x-ui/x-ui.db is missing or is a symlink." >&2
    exit 1
  }
  install -d -o root -g "${SERVICE_USER}" -m 0750 /var/lib/xui-intelligence-snapshot
  # One explicit root-run backup validates the actual source before a timer is enabled.
  "${APP_DIR}/venv/bin/python" -m xui_intelligence.snapshot_exporter
  install -m 0644 -o root -g root "${SCRIPT_DIR}/systemd/xui-intelligence-snapshot.service" \
    /etc/systemd/system/xui-intelligence-snapshot.service
  install -m 0644 -o root -g root "${SCRIPT_DIR}/systemd/xui-intelligence-snapshot.timer" \
    /etc/systemd/system/xui-intelligence-snapshot.timer
fi

systemctl daemon-reload
systemctl enable --now xui-intelligence.service
if ((WITH_XUI_SNAPSHOT)); then
  systemctl enable --now xui-intelligence-snapshot.timer
fi

printf '\nInstalled X-UI Intelligence.\n'
printf 'Config: %s/config.toml\n' "${CONFIG_DIR}"
printf 'Telegram secrets: %s/xui-intelligence.env\n' "${CONFIG_DIR}"
printf 'Service: systemctl status xui-intelligence\n'
printf 'After editing config/secrets: sudo systemctl restart xui-intelligence\n'
printf 'The installer does not restart or modify x-ui or xray.\n'
