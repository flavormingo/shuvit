#!/bin/bash
set -euo pipefail
umask 077

BACKUP_DIR="/var/backups/shuvit"
KEEP_DAYS=14
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR"
cd /tmp

sudo -u postgres pg_dump -Fc shuvit > "$BACKUP_DIR/.db-$STAMP.tmp"
mv "$BACKUP_DIR/.db-$STAMP.tmp" "$BACKUP_DIR/db-$STAMP.dump"

cp /opt/shuvit/backend/.env "$BACKUP_DIR/env-$STAMP"

find "$BACKUP_DIR" -type f -mtime +"$KEEP_DAYS" -delete

echo "Backup $STAMP complete: $(du -sh "$BACKUP_DIR" | cut -f1) in $BACKUP_DIR"
