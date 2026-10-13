# Verification record

Release: GymOS Enterprise 1.0.0 source distribution. Checks performed on October 12–13, 2026, in a Linux build environment with Python 3.12.14 and Node.js 24.19.0.

This record distinguishes checks actually executed from tests and deployment instructions supplied for you to run. The release is not certified for production deployment.

## Executed checks

| Check | Observed result |
|---|---|
| Backend acceptance and domain suite | **17 passed, 3 skipped**, with one non-failing Starlette TestClient deprecation warning. |
| PostgreSQL-compatible integration environment | Tests used PGlite's PostgreSQL engine through its socket adapter and psycopg. This was not a native PostgreSQL server. |
| Schema migrations | Initial migration applied successfully. `alembic check` reported no pending schema differences. Models define 37 tables; OpenAPI contains 73 unique API paths. |
| Data persistence | Counts for members, memberships, payments and attendance matched after stopping and restarting the test database process against the same data directory. |
| Frontend tests | **8 passed** across two Vitest files, including decimal form input, backend error display, stable request keys on retry, typed fields, pagination and API-client behavior. |
| Frontend production build | `tsc -b && vite build` passed after the final retry fix. |
| Python quality | Ruff formatting and lint checks passed for the backend and scripts. |
| Configuration helper | Generated development configuration successfully; a repeat invocation preserved existing configuration. |
| Frontend runtime dependency audit | `npm audit --omit=dev` reported zero known vulnerabilities at audit time. |
| Python runtime dependency audit | `pip-audit` checked 32 locked dependencies and reported zero vulnerable dependencies at audit time. |

Backend coverage includes a complete member-to-membership-to-invoice-to-payment-to-attendance workflow; connection restart behavior; tenant isolation; role, branch and member privacy; refresh/session behavior; QR replay rejection; billing/refund rules; membership lifecycle rules; trainer booking conflicts; stock and maintenance operations; notification deduplication; and exact decimal/date calculations. Dependency audit results are a point-in-time check, not a guarantee that future advisories or application-level defects are absent.

## Three skipped backend tests

1. Immutable-event trigger rollback: the PGlite socket adapter's recovery after a database exception differs from native PostgreSQL. The database trigger and native test are supplied, but this test was skipped in the PGlite run.
2. Concurrent payment requests using the same idempotency key: requires native PostgreSQL transactions.
3. Concurrent check-ins for the same member: requires native PostgreSQL transactions.

Run the full suite against the disposable native PostgreSQL service described in `TESTING.md`. Do not set `TEST_PGLITE=1` for that run; it would skip these checks.

## Supplied but not executed here

- Windows `start.bat` execution and Windows-specific dependency installation.
- Native PostgreSQL 17 integration and concurrency checks, including refresh rotation under competing requests.
- Playwright browser acceptance, visual review, keyboard navigation and a full accessibility audit.
- Production Docker image builds, HTTPS deployment and operational smoke tests.
- SMTP delivery through a real provider, and the backup/restore drill.
- Remote CI, load testing, penetration testing, and an independent security review.

`FEATURE_STATUS.md` lists implementation boundaries separately, including manual payment recording, in-app reminders, fixed roles and renewal-time plan changes. Follow `DEPLOYMENT.md` and complete the remaining environment-specific checks before a public rollout.

## Archive contents

The archive contains application source, dependency locks, database migrations, tests, example configuration, local launchers, deployment configuration, the generated OpenAPI specification, and documentation. Development credentials, actual `.env` files, test database contents, installed dependencies and build caches are excluded. First-time setup installs dependencies and generates local development secrets.
