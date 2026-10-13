# GymOS Enterprise

A database-backed gym operations application with React, TypeScript, Vite, Tailwind, FastAPI, SQLAlchemy 2.x, Alembic and PostgreSQL. Built for local development on Windows, with separate deployment configuration.

**Start here:** install the prerequisites below, extract this entire folder, then double-click `start.bat`. The ZIP contains source code, not a standalone Windows executable. First setup needs an internet connection.

## Verification status

This is a functional implementation, **not a certified or fully production-validated deployment**. The acceptance API workflow and functional tests were exercised against PGlite's PostgreSQL engine; native PostgreSQL concurrency, Windows execution, browser E2E and production Docker deployment must still pass in your environment. See [docs/VERIFICATION.md](docs/VERIFICATION.md) and [docs/FEATURE_STATUS.md](docs/FEATURE_STATUS.md) for exact results and remaining limits.

## Windows: first-time setup

1. Install **Python 3.12 (64-bit)** from https://www.python.org/downloads/windows/. Enable the **py launcher** and **Add Python to PATH**. Open a new Command Prompt and run `py -3.12 --version`.
2. Install **Node.js 24 LTS** from https://nodejs.org/. Reopen Command Prompt and run `node --version` and `npm --version`.
3. Install **Docker Desktop** from https://docs.docker.com/desktop/setup/install/windows-install/. Use its WSL 2 backend. If Windows requests WSL, run `wsl --install` in an administrator terminal, restart Windows, and finish Docker Desktop setup. Start Docker Desktop and wait until its engine is running. Verify `docker version` and `docker compose version`.
4. Extract the ZIP into a short, writable path such as `C:\Projects\gymos-enterprise`. Do not run files inside the ZIP viewer or from `Program Files`.
5. Double-click **start.bat**. Keep the setup window open. It generates random development secrets, starts PostgreSQL, creates a Python environment, installs locked dependencies, runs migrations, creates the optional development demo, installs the frontend and starts three application windows.
6. Wait for Vite to report ready, then open **http://localhost:5173**. Keep using this hostname; do not alternate between `localhost` and `127.0.0.1` for browser sign-in.
7. Open **.local-credentials.txt** in the project root. The generated demo uses organization **demo-gym** and email **owner@example.com**, with a unique randomly generated password. No fixed administrator password is shipped.
8. Sign in. The explicitly seeded demo contains one owner, one branch and one plan. It contains **no fake members, attendance, payments or dashboard metrics**. Your entries are stored in PostgreSQL.

Python newer than 3.12 is compatible with the application design, but `start.bat` intentionally selects the tested 3.12 interpreter. To use another interpreter, create the environment manually and validate the locked dependencies first.

### Addresses

| Service | Address |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://127.0.0.1:8000/api/v1 |
| Interactive API documentation | http://127.0.0.1:8000/docs |
| Readiness | http://127.0.0.1:8000/health/ready |
| Database | 127.0.0.1:5432; credentials in root .env |

## Your first complete workflow

1. **Team & settings → Branches → Add branch.** Set the branch time zone and working hours. Equal opening/closing times mean 24-hour access.
2. **Memberships → Create plan.** For a typical plan use 30, 90, 180 or 365 days. Durations are fixed day counts, not calendar-month arithmetic.
3. **Members → Register member.** Choose the home branch and enter a unique phone number.
4. **Memberships → Assign membership.** Select the member, plan and start date. This creates the invoice and an initially pending membership.
5. **Billing & payments → Record payment.** Record actual money received manually. Partial payments leave a balance. Full payment activates membership access. A zero-price plan activates immediately.
6. **Billing → Details → Receipt.** Open the printable receipt and use your browser's Print command to save a PDF. This is a payment receipt, not a jurisdiction-specific tax invoice certification.
7. **Attendance → Check in member.** The server checks membership, branch, working hours and duplicate attendance. Check the member out at the end of the visit.
8. **Overview / Analytics & reports.** View the resulting metrics and export the date-filtered CSV report. Reload or restart the applications: records remain in the Docker database volume.

## Manual setup (Windows Command Prompt)

From the project root:

```bat
py -3.12 scripts\configure.py
docker compose up -d --wait db
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m app.seed
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In a second terminal:

```bat
cd C:\Projects\gymos-enterprise\frontend
npm ci
npm run dev
```

In a third terminal:

```bat
cd C:\Projects\gymos-enterprise\backend
.venv\Scripts\python.exe -m app.jobs
```

The jobs process creates in-app expiry, session and operational reminders. It retries failed passes with bounded backoff and deduplicates notifications in PostgreSQL. Optional SMTP absence does not prevent startup.

### Empty workspace instead of a demo

Skip `python -m app.seed` and use **Create a workspace** on the login page. Registration is enabled only in local configuration. For production, registration is disabled; run `python -m app.bootstrap` as an authorized deployment administrator.

### macOS / Linux

Install Python 3.12, Node.js 24 and Docker Compose. Run `bash scripts/start.sh` from the project root. Stop with Ctrl+C. This script starts the API and jobs processes and keeps Vite in the foreground.

## Everyday operation

- Close the three application windows to stop the API, frontend and notifications. Use `docker compose stop db` to stop the database while keeping all records.
- Running `start.bat` again preserves existing `.env` files, database contents and demo account. It does not reset your password or recreate demo data.
- Never use `docker compose down -v` on a database containing records you need: that deletes the database volume. Back up first.
- Membership dates use **[start date, end date)**. A membership ending on November 12 permits entry through November 11, subject to branch grace days.
- Refunds are recorded separately, never by deleting a payment. A refunded invoice may reopen a balance and suspend linked membership access.
- Changing plan prices affects new purchases only. Upgrade/downgrade chooses a new plan at renewal; immediate prorated plan replacement is not implemented.
- To invite a trainer, create the Trainer account with the relevant branch, activate it, then link its profile in Trainers. Assign clients before issuing a training package and booking sessions.
- To create a member login, invite the **Member** role and select its existing member profile. The portal only exposes that member's records.
- QR codes are opaque server-generated one-use tokens, valid for two minutes. The desk accepts a keyboard-wedge scanner or pasted token. Webcam scanning and physical access controllers are not integrated.

## Tests and code quality

See [docs/TESTING.md](docs/TESTING.md). Tests refuse an implicit developer database URL. Integration runs require a dedicated test database and an explicit `GYMOS_TEST_CONFIRM=isolated` flag.

## Repository

- `backend/app/api/`: authenticated REST endpoints by business module.
- `backend/app/services/`: shared billing, membership and serialization rules.
- `backend/app/models.py`: normalized tenant-aware models and constraints.
- `backend/alembic/`: versioned schema, role bootstrap and immutable-event triggers.
- `backend/tests/`: domain, acceptance, permissions, isolation and native concurrency tests.
- `frontend/src/`: React pages, common forms/tables/dialogs, API client and auth context.
- `frontend/e2e/`: Playwright owner acceptance workflow.
- `scripts/`: configuration, startup and backup helpers.
- `deploy/`, `compose.production.yaml`: deployment configuration.
- `docs/`: architecture, business rules, troubleshooting, tests, security and operational runbooks.

## Further reading

[Architecture](docs/ARCHITECTURE.md) · [Feature status](docs/FEATURE_STATUS.md) · [Business rules](docs/BUSINESS_RULES.md) · [Deployment](docs/DEPLOYMENT.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)
