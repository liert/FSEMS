#!/bin/bash
# Install FSEMS production systemd units. Run as root after deploying code to /opt/fsems.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="${FSEMS_INSTALL_DIR:-/opt/fsems}"
ENV_FILE="${FSEMS_ENV_FILE:-/etc/fsems/fsems.env}"

echo "Installing FSEMS to ${INSTALL_DIR} ..."
mkdir -p "$(dirname "$ENV_FILE")"
if [[ ! -f "$ENV_FILE" ]]; then
  install -m 0640 "$ROOT/.env.example" "$ENV_FILE"
  echo "Created ${ENV_FILE} — edit before starting services."
fi

rsync -a --delete \
  --exclude data --exclude .git --exclude frontend/node_modules --exclude backend/.venv \
  "$ROOT/" "$INSTALL_DIR/"

if [[ ! -d "$INSTALL_DIR/backend/.venv" ]]; then
  python3 -m venv "$INSTALL_DIR/backend/.venv"
  "$INSTALL_DIR/backend/.venv/bin/pip" install -r "$INSTALL_DIR/backend/requirements.txt"
fi

if [[ -f "$INSTALL_DIR/frontend/package-lock.json" ]]; then
  (cd "$INSTALL_DIR/frontend" && npm ci && npm run build)
fi

install -m 0644 "$ROOT/deploy/systemd/fsems-api.service" /etc/systemd/system/fsems-api.service
install -m 0644 "$ROOT/deploy/systemd/fsems-celery.service" /etc/systemd/system/fsems-celery.service
systemctl daemon-reload

echo "Done. Next steps:"
echo "  1. Edit ${ENV_FILE}"
echo "  2. sudo systemctl enable --now fsems-api fsems-celery"
echo "  3. Configure Nginx to proxy /api and serve frontend/dist (see README)"
