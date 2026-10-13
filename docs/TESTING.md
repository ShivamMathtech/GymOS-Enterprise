# Testing

## Frontend

```text
cd frontend
npm ci
npm run lint
npm test
npm run build
npm audit --omit=dev
```

## Backend: isolated PostgreSQL integration tests

These commands use a **separate disposable database on port 5433**. They do not use the development volume.

Windows PowerShell from the project root:

```powershell
docker compose -f compose.test.yaml up -d --wait
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
$env:TEST_DATABASE_URL = "postgresql+psycopg://gymos_test:isolated-test-only@127.0.0.1:5433/gymos_test"
$env:DATABASE_URL = $env:TEST_DATABASE_URL
$env:GYMOS_TEST_CONFIRM = "isolated"
$env:APP_ENV = "test"
$env:SECRET_KEY = "test-only-randomized-in-ci-not-a-production-secret"
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
cd ..
docker compose -f compose.test.yaml down
```

A new test organization is generated per fixture; cleanup does not delete developer tables. The dedicated test DB uses tmpfs and disappears when its container is removed. Tests require both TEST_DATABASE_URL and GYMOS_TEST_CONFIRM=isolated; no fallback to a user's development or production DB is permitted.

Linux/macOS use `backend/.venv/bin/python` and `export NAME=value` with the same variables.

## Browser acceptance

Run backend/Vite against the isolated test database with ALLOW_REGISTRATION=true. Then:

```text
cd frontend
npx playwright install chromium
npm run test:e2e
```

The supplied E2E test creates its own organization and drives registration, branch creation, plan creation, member registration, assignment, payment and check-in through the UI. Use a local disposable test server; never point this test at production. E2E tests are included but were not executed in the build environment.

## Native concurrency

`tests/test_concurrency.py` concurrently repeats a payment key and concurrently checks in the same member. Expected outcomes are one immutable payment and one open visit. These tests require native PostgreSQL transactions; the PGlite test run deliberately skips them. Do not interpret PGlite's multiplexer as equivalent proof of native row locking.

## Dependency locks

`requirements.txt` and `requirements-dev.txt` pin dependencies and hashes. `package-lock.json` locks frontend installation; use npm ci. To intentionally update Python locks, install pip-tools into a maintainer environment, update requirements.in, then run pip-compile --generate-hashes for both lockfiles and retest. Windows-only resolution and wheels should be checked on a Windows runner before release.

CI runs migrations, schema drift checks, backend tests, Ruff, frontend type checking, Vitest/build, browser acceptance and dependency auditing against its disposable PostgreSQL service. CI configuration is supplied, not an assertion that a remote CI run occurred.
