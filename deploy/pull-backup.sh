#!/bin/bash
set -euo pipefail
umask 077

DEST="$HOME/Backups/shuvit"
MEDIA="$DEST/media"
HOLDING="$DEST/media-deleted"
KEEP_DAYS=60
TODAY="$(date -u +%F)"
CUTOFF="$(date -u -v-"${KEEP_DAYS}"d +%F)"

mkdir -p "$MEDIA"

/usr/bin/rsync -a --exclude '.*' --exclude 'media-*' shuvit-vps:/var/backups/shuvit/ "$DEST/"
/usr/bin/rsync -rlt shuvit-vps:/opt/shuvit/media/ "$MEDIA/"

server_files="$(ssh -o BatchMode=yes shuvit-vps 'cd /opt/shuvit/media && find . -type f' | LC_ALL=C sort)"

if [ -n "$server_files" ]; then
    (cd "$MEDIA" && find . -type f | LC_ALL=C sort) \
        | LC_ALL=C comm -13 <(printf '%s\n' "$server_files") - \
        | while IFS= read -r path; do
            mkdir -p "$(dirname "$HOLDING/$TODAY/$path")"
            mv "$MEDIA/$path" "$HOLDING/$TODAY/$path"
        done
    find "$MEDIA" -mindepth 1 -type d -empty -delete
fi

find "$DEST" -maxdepth 1 -type f -mtime +"$KEEP_DAYS" -delete

for dir in "$HOLDING"/*/; do
    [ -d "$dir" ] || continue
    name="$(basename "$dir")"
    if [[ "$name" < "$CUTOFF" ]]; then
        rm -rf "$dir"
    fi
done

echo "$(date -u +%FT%TZ) pulled backups, $(find "$MEDIA" -type f | wc -l | tr -d ' ') media files"
