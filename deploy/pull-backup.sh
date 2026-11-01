#!/bin/bash
# Copies VPS backups to this Mac so they survive losing the server.
# Installed to ~/Library/Application Support/shuvit/ and run daily by launchd.
set -euo pipefail
umask 077

DEST="$HOME/Backups/shuvit"
KEEP_DAYS=60

mkdir -p "$DEST"
/usr/bin/rsync -a --exclude '.*' shuvit-vps:/var/backups/shuvit/ "$DEST/"
find "$DEST" -type f -mtime +"$KEEP_DAYS" -delete

echo "$(date -u +%FT%TZ) pulled backups, latest: $(ls -t "$DEST" | head -1)"
