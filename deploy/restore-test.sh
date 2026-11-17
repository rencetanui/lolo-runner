#!/usr/bin/env bash
# THE RESTORE DRILL. A backup you have never restored is only a hope.
# Restores a backup into a scratch database, prints row counts, then removes the scratch database.
# It never touches the real database.
#
#   ./restore-test.sh backups/lolo-db-20261201T020000Z.dump
set -euo pipefail
cd "$(dirname "$0")"

file="${1:?usage: ./restore-test.sh backups/lolo-db-<timestamp>.dump}"
[ -s "$file" ] || { echo "No such backup: $file" >&2; exit 1; }

env_value() { grep -E "^$1=" .env | head -n1 | cut -d= -f2- | tr -d '\r' || true; }
U=$(env_value POSTGRES_USER)
psql_db() { docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "$U" "$@"; }

echo "Creating scratch database..."
psql_db -d postgres -c "DROP DATABASE IF EXISTS restore_test"
psql_db -d postgres -c "CREATE DATABASE restore_test"

echo "Restoring $file ..."
docker compose exec -T db pg_restore -U "$U" -d restore_test --no-owner --exit-on-error < "$file"

echo "Checking the restored data:"
psql_db -d restore_test -c "
  SELECT 'users' AS what, count(*) FROM users
  UNION ALL SELECT 'events', count(*) FROM events
  UNION ALL SELECT 'registrations', count(*) FROM registrations
  UNION ALL SELECT 'payments', count(*) FROM payments
  UNION ALL SELECT 'refunds', count(*) FROM refunds
  UNION ALL SELECT 'migration', 1 FROM alembic_version;"

echo "Removing scratch database..."
psql_db -d postgres -c "DROP DATABASE restore_test"
echo "Restore drill passed. Compare the counts above with what you expect, and write today's date in your runbook."
