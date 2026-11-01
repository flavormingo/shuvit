#!/bin/bash
# Deploy Shuvit to VPS
# Usage: bash deploy/deploy.sh <vps-host>
set -euo pipefail

VPS_HOST="${1:-shuvit-vps}"
REMOTE_DIR="/opt/shuvit"

echo "=== Deploying Shuvit to ${VPS_HOST} ==="

# Sync backend
echo "Syncing backend..."
rsync -avz --delete \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude 'media_uploads' \
    backend/ "${VPS_HOST}:${REMOTE_DIR}/backend/"

# Sync pipeline
echo "Syncing pipeline..."
rsync -avz --delete \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    pipeline/ "${VPS_HOST}:${REMOTE_DIR}/pipeline/"

# Install dependencies and run migrations on remote
echo "Installing dependencies and running migrations..."
ssh "${VPS_HOST}" << 'REMOTE'
set -euo pipefail
cd /opt/shuvit

# Backend
cd backend
python3.12 -m venv .venv 2>/dev/null || true
.venv/bin/pip install --quiet -e .
.venv/bin/alembic upgrade head

# Pipeline
cd ../pipeline
python3.12 -m venv .venv 2>/dev/null || true
.venv/bin/pip install --quiet -e .

cd ..
REMOTE

# Restart services
echo "Restarting services..."
ssh "${VPS_HOST}" "sudo systemctl daemon-reload && sudo systemctl restart shuvit-api"

echo "=== Deployment complete ==="
echo "Check status: ssh ${VPS_HOST} 'systemctl status shuvit-api'"
