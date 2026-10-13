# Architecture

## Runtime

React 19 / TypeScript / Vite serve the client. TanStack Query caches authenticated queries. The shared API client keeps the short-lived access token only in memory, refreshes through an HttpOnly cookie, and sends CSRF tokens on cookie-authenticated refresh/logout calls. Refresh is single-flight within a tab.

FastAPI exposes `/api/v1`. Synchronous route functions and synchronous SQLAlchemy sessions are used consistently; FastAPI dispatches these routes through its thread pool. No synchronous database calls are mixed into async route handlers. Middleware handles CORS/origin policy, request IDs, structured metadata-only logs and safe error envelopes.

Each request obtains one transactional SQLAlchemy Session. Write dependencies commit before the response is sent (`scope='function'`). Failure rolls back. No application startup path calls `create_all`. Alembic is the sole schema installation/update mechanism.

A separate `python -m app.jobs` process creates deduplicated in-app notifications. It does not require Redis or an external delivery provider. PostgreSQL unique keys allow restart/retry of a whole reminder pass.

## Module boundaries

| Module | Responsibility |
|---|---|
| auth / security / deps | Identity, sessions, role/permission resolution, organization and branch access |
| crm | Organizations, branches, member profiles, CSV and photos |
| memberships service | Date state, overlapping access, renewals, freezes and extensions |
| billing service | Exact line totals, sequential invoices, payment/refund idempotency and activation |
| attendance | Eligibility, check-in/out and server-generated QR validation |
| resources / operations | Catalog DTOs and policies, trainer booking locks, inventory and maintenance transactions |
| reports / portal | Scoped reporting and member-only read surfaces |
| jobs | Idempotent reminder production and expired transient token cleanup |

## Tenant isolation

Every business table carries `org_id`. Organization identifiers come from the authenticated user/session; clients cannot choose an organization in a business payload. Lookups require `(id, org_id)`, and branch-restricted roles receive only their assigned branches. Trainer queries additionally require assigned members. Member accounts access only their linked profile.

Composite foreign keys include `org_id`, preventing cross-organization relationships at the database layer. This complements application query filters; PostgreSQL row-level security is not enabled in this version. Direct database access must therefore be limited to trusted operational roles.

SQLAlchemy models define 37 normalized tables, including roles/permissions and one-time token records. Consult generated OpenAPI and `models.py` for the authoritative schemas. Response projections use explicit public-field whitelists rather than serializing ORM `__dict__` values. Sensitive user hashes/tokens and member private fields are excluded by policy.

## Concurrent operations

- Member row lock serializes membership assignment, overlapping-date changes and check-in.
- Organization row lock serializes member/invoice sequence allocation and ownership changes.
- Invoice row lock serializes payments/refunds and checks net balance.
- Trainer row lock plus member row lock serializes booking/conflict checks; package use is checked within the same transaction.
- Stock item row lock guards stock updates. A database check prevents negative stock.
- A PostgreSQL partial unique index allows at most one open attendance record per member.
- Idempotency keys have organization-scoped unique constraints. Reusing a payment key with different payload returns 409.
- Append-only events are protected by PostgreSQL triggers on payments, refunds, invoice items, stock movements, membership events and audit logs.

Native PostgreSQL concurrency tests are provided and must be run before production. PGlite's multiplexed connection model does not establish native lock behavior.

## API conventions

Amounts are decimal strings. Inputs reject unknown fields. Dates use ISO 8601; timestamp inputs require offsets where business logic needs an instant. Most large lists return `{items,total,page,size}` with page size 1–100. Small catalogs such as branches/plans are arrays. See `/docs` for exact operations and body schemas.

Typical failure: `{ "error": { "code": "validation_error", "message": "Check the supplied fields", "fields": [{"field":"body.amount","message":"..."}], "request_id":"..." } }`.

## References consulted

- FastAPI authentication: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- PostgreSQL row locking: https://www.postgresql.org/docs/17/explicit-locking.html
- PostgreSQL release line: https://www.postgresql.org/docs/17/release.html
- PGlite socket testing limitations: https://pglite.dev/docs/pglite-socket
