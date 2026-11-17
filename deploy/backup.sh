#!/usr/bin/env bash
# Back up the database and the uploaded images. Run it by hand, or from cron, for example:
#   0 2 * * * /srv/lolo-runner/deploy/backup.sh >> /var/log/lolo-backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")"

# Read single values from .env without "sourcing" it (some values contain characters bash would mangle).
env_value() { grep -E "^$1=" .env | head -n1 | cut -d= -f2- | tr -d '\r' || true; }
POSTGRES_USER=$(env_value POSTGRES_USER)
POSTGRES_DB=$(env_value POSTGRES_DB)
KEEP_DAYS=$(env_value BACKUP_KEEP_DAYS); KEEP_DAYS=${KEEP_DAYS:-14}
RCLONE_REMOTE=$(env_value BACKUP_RCLONE_REMOTE)

mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
db_file="backups/lolo-db-${stamp}.dump"
media_file="backups/lolo-media-${stamp}.tgz"

# Database: PostgreSQL's compressed "custom" format, written to a temporary name first so a half-finished
# file can never be mistaken for a good backup.
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "${db_file}.partial"
[ -s "${db_file}.partial" ] || { echo "ERROR: the database backup is empty" >&2; rm -f "${db_file}.partial"; exit 1; }
mv "${db_file}.partial" "$db_file"

# Uploaded images (banner photos).
docker run --rm -v lolo-runner_media:/data:ro -v "$PWD/backups":/out alpine \
  tar czf "/out/$(basename "$media_file")" -C /data .

# Delete local backups older than KEEP_DAYS.
find backups -name 'lolo-*' -mtime +"$KEEP_DAYS" -delete

# Optional off-site copy. A backup on the same server is lost together with the server.
if [ -n "$RCLONE_REMOTE" ]; then
  if command -v rclone >/dev/null 2>&1; then
    rclone copy "$db_file" "$RCLONE_REMOTE"
    rclone copy "$media_file" "$RCLONE_REMOTE"
  else
    echo "WARNING: BACKUP_RCLONE_REMOTE is set but rclone is not installed. Nothing was copied off-site." >&2
  fi
fi

echo "$(date -u +%FT%TZ) backup ok: $db_file ($(du -h "$db_file" | cut -f1)), $media_file"
