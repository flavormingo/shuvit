#!/bin/bash
set -euo pipefail
umask 077

DEST="$HOME/Backups/shuvit"
KEEP_DAYS=60

mkdir -p "$DEST"
/usr/bin/rsync -a --exclude '.*' shuvit-vps:/var/backups/shuvit/ "$DEST/"
find "$DEST" -type f -mtime +"$KEEP_DAYS" -delete

echo "$(date -u +%FT%TZ) pulled backups, latest: $(ls -t "$DEST" | head -1)"
