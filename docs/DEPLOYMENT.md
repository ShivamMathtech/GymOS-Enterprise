# Deployment and operational runbook

## Release gates

Before deployment: run native PostgreSQL integration/concurrency tests, execute Playwright acceptance in supported browsers, validate Windows setup if applicable, audit dependencies and container images, review privacy/retention requirements, exercise backup/restore, and load-test expected workloads. The provided package has not passed these environment-specific production gates.

## Prepare a production environment

1. Provision a supported Linux/Docker host and a DNS name you control.
2. Use distinct production DB credentials and a random signing secret. Copy root `.env.example` to `.env` and fill its values. Copy `backend/.env.production.example` to `backend/.env.production`; its DB hostname is **db**, not localhost.
3. Set APP_ENV=production, COOKIE_SECURE=true, ALLOW_REGISTRATION=false, FRONTEND_URL=https://your-domain and ALLOWED_ORIGINS to that exact origin. Do not copy a development .env or demo credential file.
4. Configure SMTP for password recovery if needed. Never expose dev-outbox or upload storage directly. Use a controlled database role and encrypted disks/backups.
5. Review images in Compose and Dockerfiles. PostgreSQL is pinned to the 17.11 patch line. Resolve image digests after testing for stronger deployment reproducibility; Python and Node base tags still receive updates.
6. Run `docker compose -f compose.production.yaml build` and `docker compose -f compose.production.yaml up -d`.
7. Compose waits for DB readiness, runs migrations once through a separate service, then starts API, jobs and static frontend. No schema creation occurs in application startup.
8. Create the first organization interactively: `docker compose -f compose.production.yaml exec api python -m app.bootstrap`. The password is entered through getpass, not command-line arguments.
9. Put a TLS reverse proxy in front of 127.0.0.1:8080; `deploy/Caddyfile.example` shows a host Caddy example. The web container is only bound to loopback. Expose only your TLS proxy to clients. The production DB and API have no published ports.
10. Sign in, create branches and staff, and verify the complete acceptance workflow before onboarding real members.

## Migration and rollback

- Back up DB and uploads before migration. Review generated revisions and SQL (`alembic upgrade head --sql`) in staging.
- `alembic upgrade head` applies the schema. `alembic current` and `alembic check` confirm status and model drift.
- Initial migration `0001` creates all tables, constraints, reference roles and immutable-event triggers. Downgrading it to `base` **drops all application tables**. Never use this to roll back a live installation.
- Prefer forward corrective migrations. For an incompatible release, restore a verified pre-upgrade backup to a new database and switch application traffic after validating it. Do not mutate migration history after rollout.

## Backup and restore

`scripts/backup.py` invokes pg_dump inside the chosen Compose database and writes binary output directly, avoiding PowerShell redirection corruption. Run from the project root:

```text
python scripts/backup.py backups/gymos-2026-10-12.dump
python scripts/backup.py backups/gymos-2026-10-12.dump --compose compose.production.yaml
```

Backups contain personal information. Restrict ACLs, encrypt them and move copies off-host under your retention policy. Back up the uploads volume at the same consistency point (or briefly stop writes). Database dumps do not contain photo bytes.

Restore into a **new empty database**, not over the live database. `scripts/restore.py` requires a destination database name ending in `_restore` and refuses the configured live name. It creates the restore database and imports a custom-format dump. Example:

```text
python scripts/restore.py backups/gymos-2026-10-12.dump --database gymos_restore
```

After restore: run read-only counts, compare invoice balances, check representative member photos with the corresponding upload backup, and perform a staged acceptance run. Switch connection strings only through your reviewed deployment process. Record restore duration and data loss window. A restore drill was not executed in the build environment.

## Monitoring / incidents

- Poll `/health/live` for process health, `/health/ready` for DB/migration readiness. Restrict external detailed operational endpoints at the proxy if required.
- Track request status/duration, DB connections, disk usage, pending invoices, failed job passes and notification generation freshness. Use request IDs for triage.
- Use container restart policies and central log collection. Configure log rotation (for example Docker json-file max-size 10m, max-file 5) in your host daemon or deployment override; API logs contain metadata, not bodies.
- If DB is unavailable: stop accepting new writes, inspect DB health/disk/credentials, restore connectivity, then retry idempotent payments with their original key. Do not assume a client timeout means no payment was recorded.
- For suspicious account use: revoke its sessions, disable the account, invalidate outstanding action tokens, review audit records, rotate exposed secrets and follow your incident policy.
- If a job fails, it retries after bounded backoff. Dedupe keys prevent duplicate in-app reminders across restarts. No money movement is performed by jobs.

## Privacy and retention

Minimize member notes and progress data. Access is role- and assignment-scoped; financial/history records remain for audit. Archive a member to stop access without deleting history. Set an organization-specific documented retention schedule and lawful erasure process with your advisers. No automatic legal-retention promise is made.

Expired QR tokens are cleaned after one day, action tokens after seven days, refresh sessions after 30 days past expiry, and rate buckets after expiry. Business records and immutable audit/financial events are not automatically purged. De-identification/export and legally required deletion need a reviewed administrative migration and matching backup policy. Optional old-photo cleanup must first confirm no current member references the file.
