#!/bin/bash
set -euo pipefail
umask 077

DEST="$HOME/Backups/shuvit"
KEEP_DAYS=60
TODAY="$(date -u +%F)"
CUTOFF="$(date -u -v-"${KEEP_DAYS}"d +%F)"

mkdir -p "$DEST/media"

/usr/bin/rsync -a --exclude '.*' --exclude 'media-*' shuvit-vps:/var/backups/shuvit/ "$DEST/"

/usr/bin/rsync -a --delete --backup --backup-dir="$DEST/media-deleted/$TODAY" \
    shuvit-vps:/opt/shuvit/media/ "$DEST/media/"

find "$DEST" -maxdepth 1 -type f -mtime +"$KEEP_DAYS" -delete

for dir in "$DEST"/media-deleted/*/; do
    [ -d "$dir" ] || continue
    name="$(basename "$dir")"
    if [[ "$name" < "$CUTOFF" ]]; then
        rm -rf "$dir"
    fi
done

echo "$(date -u +%FT%TZ) pulled backups, $(find "$DEST/media" -type f | wc -l | tr -d ' ') media files"
