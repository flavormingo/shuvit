#!/bin/bash
# Shuvit VPS Setup Script — Ubuntu 24
# Run as root on a fresh VPS
set -euo pipefail

echo "=== Shuvit VPS Setup ==="

# System updates
apt update && apt upgrade -y

# Essential packages
apt install -y \
    build-essential \
    curl \
    git \
    ufw \
    fail2ban \
    unattended-upgrades \
    software-properties-common

# PostgreSQL 16 + PostGIS
apt install -y postgresql-16 postgresql-16-postgis-3 postgresql-client-16

# Redis
apt install -y redis-server
systemctl enable redis-server

# Python 3.12
add-apt-repository -y ppa:deadsnakes/ppa
apt install -y python3.12 python3.12-venv python3.12-dev

# Nginx
apt install -y nginx

# Certbot
apt install -y certbot python3-certbot-nginx

# Firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow http
ufw allow https
echo "y" | ufw enable

# Create app user
if ! id -u shuvit &>/dev/null; then
    useradd -m -s /bin/bash shuvit
fi

# Create app directory
mkdir -p /opt/shuvit
chown shuvit:shuvit /opt/shuvit

# Create media directory
mkdir -p /opt/shuvit/media
chown shuvit:shuvit /opt/shuvit/media

# Setup PostgreSQL
sudo -u postgres psql -c "CREATE USER shuvit WITH PASSWORD 'CHANGE_ME_IN_PRODUCTION';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE shuvit OWNER shuvit;" 2>/dev/null || true
sudo -u postgres psql -d shuvit -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Configure Redis for memory limits (suitable for 2GB VPS)
cat > /etc/redis/redis.conf.d/shuvit.conf << 'REDIS_CONF'
maxmemory 256mb
maxmemory-policy allkeys-lru
REDIS_CONF
mkdir -p /etc/redis/redis.conf.d
systemctl restart redis-server

# Fail2ban config
systemctl enable fail2ban
systemctl start fail2ban

# Install systemd services
echo "=== Copy systemd services from deploy/systemd/ ==="
echo "=== Copy nginx config from deploy/nginx/ ==="
echo ""
echo "=== VPS setup complete ==="
echo "Next steps:"
echo "  1. Copy .env to /opt/shuvit/.env"
echo "  2. Copy systemd services: cp deploy/systemd/* /etc/systemd/system/"
echo "  3. Copy nginx config: cp deploy/nginx/shuvit.conf /etc/nginx/sites-available/"
echo "  4. ln -s /etc/nginx/sites-available/shuvit.conf /etc/nginx/sites-enabled/"
echo "  5. Run certbot: certbot --nginx -d api.shuvit.app"
echo "  6. Deploy app: bash deploy/deploy.sh"
