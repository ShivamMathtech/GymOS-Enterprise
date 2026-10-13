import os, secrets
import pytest
from uuid import uuid4

# Never fall back to a developer's DATABASE_URL. Integration tests require explicit opt-in.
TEST_URL = os.environ.get("TEST_DATABASE_URL")
os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = secrets.token_hex(32)
os.environ["DATABASE_URL"] = TEST_URL or "postgresql+psycopg://unused:unused@127.0.0.1:1/gymos_test"
os.environ["AUTH_RATE_LIMIT"] = "10000"
os.environ["ALLOW_REGISTRATION"] = "true"


@pytest.fixture
def client():
    if not TEST_URL:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated, migrated test database")
    if os.environ.get("GYMOS_TEST_CONFIRM") != "isolated":
        pytest.fail("GYMOS_TEST_CONFIRM=isolated is required")
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def owner(client):
    suffix = uuid4().hex[:12]
    data = {
        "organization": "Test Club",
        "slug": "test-" + suffix,
        "name": "Test Owner",
        "email": suffix + "@example.com",
        "password": "Strong-test-password-42",
    }
    r = client.post("/api/v1/auth/register", json=data)
    assert r.status_code == 201, r.text
    client.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    branch = client.post(
        "/api/v1/branches", json={"name": "Main", "opens": "00:00", "closes": "00:00", "timezone": "UTC"}
    )
    assert branch.status_code == 201, branch.text
    return {"client": client, "branch": branch.json(), "registration": data, "auth": r.json()}


@pytest.fixture
def member(owner):
    c = owner["client"]
    r = c.post(
        "/api/v1/members",
        json={
            "branch_id": owner["branch"]["id"],
            "name": "Alex Member",
            "phone": "+919800000001",
            "email": "member@example.com",
            "notes": "Restricted notes",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def subscription(owner, member):
    from datetime import datetime, timezone

    c = owner["client"]
    p = c.post(
        "/api/v1/plans",
        json={"name": "Monthly", "duration_days": 30, "price": "1000.00", "discount": "100.00", "tax_rate": "18.00"},
    )
    assert p.status_code == 201, p.text
    payload = {
        "member_id": member["id"],
        "plan_id": p.json()["id"],
        "start_date": datetime.now(timezone.utc).date().isoformat(),
        "request_key": str(uuid4()),
    }
    r = c.post("/api/v1/memberships", json=payload)
    assert r.status_code == 201, r.text
    inv = c.get("/api/v1/invoices").json()["items"][0]
    return {"membership": r.json(), "plan": p.json(), "invoice": inv, "payload": payload}
