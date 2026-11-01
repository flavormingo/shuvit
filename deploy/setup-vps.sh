#!/bin/bash
set -euo pipefail

echo "=== Shuvit VPS Setup ==="

apt update && apt upgrade -y

apt install -y \
    build-essential \
    curl \
    git \
    ufw \
    fail2ban \
    unattended-upgrades \
    software-properties-common \
    ffmpeg

apt install -y postgresql-16 postgresql-16-postgis-3 postgresql-client-16

apt install -y redis-server
systemctl enable redis-server

add-apt-repository -y ppa:deadsnakes/ppa
apt install -y python3.12 python3.12-venv python3.12-dev

apt install -y nginx

apt install -y certbot python3-certbot-nginx

ufw default deny incoming
ufw default allow outgoing
ufw allow 22022/tcp
ufw allow http
ufw allow https
echo "y" | ufw enable

if ! id -u shuvit &>/dev/null; then
    useradd -m -s /bin/bash shuvit
fi

mkdir -p /opt/shuvit
chown shuvit:shuvit /opt/shuvit

mkdir -p /opt/shuvit/media
chown shuvit:shuvit /opt/shuvit/media

sudo -u postgres psql -c "CREATE USER shuvit WITH PASSWORD 'CHANGE_ME_IN_PRODUCTION';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE shuvit OWNER shuvit;" 2>/dev/null || true
sudo -u postgres psql -d shuvit -c "CREATE EXTENSION IF NOT EXISTS postgis;"

cat > /etc/redis/redis.conf.d/shuvit.conf << 'REDIS_CONF'
maxmemory 256mb
maxmemory-policy allkeys-lru
REDIS_CONF
mkdir -p /etc/redis/redis.conf.d
systemctl restart redis-server

systemctl enable fail2ban
systemctl start fail2ban

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
