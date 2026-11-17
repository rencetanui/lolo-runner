# Lolo Runner: deployment runbook

One server runs everything with Docker Compose: PostgreSQL, the API, the background worker, and Caddy (which serves
the website over HTTPS and forwards API calls). Run every command below from this `deploy/` folder.

## First deployment

1. **Server.** An Ubuntu LTS VPS (2 vCPU / 4 GB RAM is plenty for a first season) with daily provider snapshots.
   Log in with an SSH key, create a non-root user, turn off password login, and open only ports 22, 80 and 443
   (`ufw allow 22,80,443/tcp`, `ufw allow 443/udp`, `ufw enable`).
   Docker published ports bypass `ufw`, so never add a `ports:` entry to the database service.
2. **Docker.** Install Docker Engine and the Compose plugin by following the official instructions at
   docs.docker.com/engine/install/ubuntu, then `docker compose version` should work.
3. **DNS.** Point an A record for your domain at the server's IP address and wait for it to propagate.
   Caddy cannot get a certificate until it does.
4. **Code and settings.**
   ```bash
   sudo mkdir -p /srv && sudo chown $USER /srv && cd /srv
   git clone <your repository URL> lolo-runner && cd lolo-runner/deploy
   cp .env.example .env && chmod 600 .env
   nano .env            # fill in every value; the comments explain each one
   ```
   The app **refuses to start** if a setting is unsafe (a short secret, plain-HTTP URLs, the mock M-Pesa on a
   production server, and so on) and prints exactly what to fix.
5. **Start.**
   ```bash
   docker compose up -d --build
   docker compose ps                      # api should become "healthy"; "migrate" exits after it finishes
   docker compose logs --tail=50 migrate api worker
   ```
6. **First admin.** Open the site, sign up, then promote your account:
   ```bash
   docker compose exec api python -m scripts.set_role you@example.com admin
   ```
   Never run `scripts.seed_events` on production: it creates fake races.
7. **Backups and monitoring** (below), then go through the go-live checklist.

## Updating

```bash
./deploy.sh
```

It backs up, pulls the latest code, rebuilds, restarts, runs database migrations automatically and waits until
the API is ready. If a deploy goes wrong:

```bash
git -C .. log --oneline -5               # find the last good commit
git -C .. checkout <good commit>
docker compose up -d --build
```

Migrations only move forward. If a migration itself caused the problem, restore the backup taken at the start of
the deploy (see "Restoring" below) and ask for help before running anything else.

## Backups

```bash
./backup.sh                               # writes backups/lolo-db-<time>.dump and backups/lolo-media-<time>.tgz
crontab -e                                # then add the line below to run it every night at 02:00 UTC
0 2 * * * /srv/lolo-runner/deploy/backup.sh >> /var/log/lolo-backup.log 2>&1
```

A backup on the same server dies with the server. Set `BACKUP_RCLONE_REMOTE` in `.env` and install `rclone`
(`rclone config` sets up an S3-compatible store such as Backblaze B2, Cloudflare R2 or AWS S3; use rclone's
`crypt` remote so the copies are encrypted, because they contain personal data).

### The restore drill (do this before launch, then every quarter)

```bash
./restore-test.sh backups/lolo-db-<timestamp>.dump
```

It restores into a scratch database, prints row counts and deletes the scratch database. Write the date and the
result in your runbook. Also try restoring onto a different machine once, to prove you can rebuild from nothing.

### Restoring for real

Stop the app, restore into the real database, start the app. Practise it on staging first.

```bash
docker compose stop api worker web
docker compose exec -T db psql -U <POSTGRES_USER> -d postgres -c "DROP DATABASE <POSTGRES_DB>" -c "CREATE DATABASE <POSTGRES_DB>"
docker compose exec -T db pg_restore -U <POSTGRES_USER> -d <POSTGRES_DB> --no-owner < backups/lolo-db-<timestamp>.dump
docker compose up -d
```

Uploaded images are in `backups/lolo-media-<timestamp>.tgz`. Unpack it into the `lolo-runner_media` volume.

Deleted accounts stay in older backups until those rotate out (`BACKUP_KEEP_DAYS`). Your Privacy Notice must say so.

## Monitoring

Create two checks in an uptime service (UptimeRobot, Better Stack and similar), each alerting by email and SMS:

| URL | Goes red when |
| --- | --- |
| `https://<domain>/health/ready` | the API or its database is down |
| `https://<domain>/health/worker` | the background worker has stopped, or messages are piling up unsent |

Put the Sentry DSN in `.env` for error reports. Also watch disk space (your provider's monitoring is fine).

## Everyday commands

```bash
docker compose ps                         # what is running
docker compose logs -f api worker         # follow logs
docker compose exec api python -m scripts.notification_status       # outgoing message queue
docker compose exec api python -m scripts.set_role someone@example.com organizer
docker compose restart worker             # after changing .env, run: docker compose up -d
```

## Staging

Use a second server (or a second folder with a different `COMPOSE_PROJECT_NAME`) with its own `.env`:
`ENVIRONMENT=staging`, a staging domain, `MPESA_ENV=sandbox`, the Africa's Talking sandbox, and a Google client
whose origin is the staging domain. Never copy production data into staging: it contains personal data.
Run `python -m scripts.seed_events` there for sample races.

## Troubleshooting

| Symptom | Look at |
| --- | --- |
| The site will not load over HTTPS | `docker compose logs web`: usually DNS not pointing at the server yet, or ports 80/443 closed |
| `api` keeps restarting | `docker compose logs api`: the message lists unsafe or missing settings |
| 502 from the site | `docker compose ps`; is `api` healthy? |
| Emails or SMS not arriving | `scripts.notification_status`, then the worker logs |
| Daraja callbacks not arriving | the callback URL is `https://<domain>/api/v1/payments/callbacks/stk/<MPESA_CALLBACK_SECRET>` |
