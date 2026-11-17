#!/usr/bin/env bash
# Update a running site: back up, fetch the latest code, rebuild, restart. Database migrations run by themselves.
# For the very first deployment, follow README.md instead (there is nothing to back up yet).
set -euo pipefail
cd "$(dirname "$0")"

echo "1/4 Backing up..."
./backup.sh

echo "2/4 Fetching the latest code..."
git -C .. pull --ff-only

echo "3/4 Building and restarting..."
docker compose build --pull
docker compose up -d

echo "4/4 Waiting for the API to become ready..."
for _ in $(seq 1 30); do
  if docker compose exec -T api python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)" >/dev/null 2>&1; then
    docker compose ps
    echo "Deployed. The API is ready."
    exit 0
  fi
  sleep 2
done
echo "The API did not become ready. Look at the logs:" >&2
echo "  docker compose logs --tail=100 migrate api" >&2
exit 1
