#!/bin/bash
# Deploy Shuvit to the VPS. Run from the repo root.
# Usage: bash deploy/deploy.sh [ssh-host]
#
# The default host is an alias in ~/.ssh/config:
#   Host shuvit-vps
#     HostName 209.74.85.177
#     Port 22022
#     User root
#     IdentityFile ~/.ssh/shuvit_vps
set -euo pipefail

VPS_HOST="${1:-shuvit-vps}"
REMOTE_DIR="/opt/shuvit"
# /health doesn't touch the database, so check an endpoint that does.
HEALTH_URL="https://api.shuvit.app/api/v1/parks?limit=1"

RSYNC_EXCLUDES=(
    --exclude '.venv'
    --exclude '__pycache__'
    --exclude '*.pyc'
    --exclude '*.egg-info'
    --exclude '.DS_Store'
    --exclude '._*'
    --exclude '.pytest_cache'
)

echo "=== Deploying Shuvit to ${VPS_HOST} ==="

echo "Backing up before deploy..."
ssh "${VPS_HOST}" "/usr/local/bin/shuvit-backup"

echo "Syncing backend..."
rsync -az --delete "${RSYNC_EXCLUDES[@]}" \
    --exclude '.env' \
    --exclude 'media_uploads' \
    backend/ "${VPS_HOST}:${REMOTE_DIR}/backend/"

echo "Syncing pipeline..."
rsync -az --delete "${RSYNC_EXCLUDES[@]}" \
    pipeline/ "${VPS_HOST}:${REMOTE_DIR}/pipeline/"

echo "Syncing website..."
rsync -az --delete --exclude '.DS_Store' site/ "${VPS_HOST}:${REMOTE_DIR}/site/"

echo "Installing system files..."
scp -q deploy/nginx/shuvit.conf "${VPS_HOST}:/etc/nginx/sites-available/shuvit"
scp -q deploy/backup.sh "${VPS_HOST}:/usr/local/bin/shuvit-backup"
scp -q deploy/systemd/shuvit-api.service deploy/systemd/shuvit-backup.service \
    deploy/systemd/shuvit-backup.timer deploy/systemd/shuvit-pipeline.service \
    deploy/systemd/shuvit-pipeline.timer "${VPS_HOST}:/etc/systemd/system/"

echo "Installing dependencies and running migrations..."
ssh "${VPS_HOST}" << 'REMOTE'
set -euo pipefail
chmod 700 /usr/local/bin/shuvit-backup
nginx -t -q
systemctl reload nginx
command -v ffmpeg >/dev/null || apt-get install -y -qq ffmpeg

cd /opt/shuvit/backend
python3.12 -m venv .venv 2>/dev/null || true
.venv/bin/pip install --quiet -e .
.venv/bin/alembic upgrade head

cd /opt/shuvit/pipeline
python3.12 -m venv .venv 2>/dev/null || true
.venv/bin/pip install --quiet -e .
REMOTE

echo "Restarting API..."
ssh "${VPS_HOST}" "systemctl daemon-reload && systemctl restart shuvit-api"

echo "Checking health..."
for _ in $(seq 1 15); do
    if [ "$(curl -s -m 5 -o /dev/null -w '%{http_code}' "${HEALTH_URL}")" = "200" ]; then
        echo "=== Deployment complete: ${HEALTH_URL} is healthy ==="
        exit 0
    fi
    sleep 2
done

echo "!!! ${HEALTH_URL} is not healthy. Check: ssh ${VPS_HOST} journalctl -u shuvit-api -n 50" >&2
exit 1
