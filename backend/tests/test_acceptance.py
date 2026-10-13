from uuid import uuid4
from decimal import Decimal
from datetime import date, timedelta, datetime, timezone
import pytest
from urllib.parse import urlparse, parse_qs

pytestmark = pytest.mark.integration


def pay(c, invoice, amount, idem=None):
    return c.post(
        "/api/v1/payments",
        json={"invoice_id": invoice["id"], "amount": amount, "method": "cash", "idempotency_key": idem or str(uuid4())},
    )


def test_complete_acceptance_and_restart(owner, member, subscription):
    c = owner["client"]
    invoice = subscription["invoice"]
    assert invoice["total"] == "1062.00"
    assert subscription["membership"]["status"] == "pending_payment"
    req = {"member_id": member["id"], "branch_id": owner["branch"]["id"]}
    assert c.post("/api/v1/attendance/check-in", json=req).status_code == 409
    p = pay(c, invoice, "400.00")
    assert p.status_code == 201, p.text
    assert c.get("/api/v1/invoices/" + invoice["id"]).json()["balance"] == "662.00"
    p = pay(c, invoice, "662.00")
    assert p.status_code == 201, p.text
    receipt = c.get("/api/v1/payments/" + p.json()["id"] + "/receipt")
    assert receipt.status_code == 200 and "1062" not in receipt.text and "662.00" in receipt.text
    assert c.get("/api/v1/memberships").json()["items"][0]["status"] == "active"
    attendance = c.post("/api/v1/attendance/check-in", json=req)
    assert attendance.status_code == 201, attendance.text
    assert c.post("/api/v1/attendance/check-in", json=req).status_code == 409
    assert c.post("/api/v1/attendance/" + attendance.json()["id"] + "/check-out").status_code == 200
    report = c.get("/api/v1/reports/dashboard")
    assert report.status_code == 200, report.text
    assert report.json()["active_members"] == 1 and Decimal(report.json()["cash_collected"]) == Decimal("1062")
    assert c.get("/api/v1/reports/export").status_code == 200
    assert member["name"] in c.get("/api/v1/members/export").text
    # Reopen DB connections and API client. No in-memory store can satisfy this read.
    from app.db import engine

    engine.dispose()
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as fresh:
        data = owner["registration"]
        login = fresh.post(
            "/api/v1/auth/login",
            json={"organization": data["slug"], "email": data["email"], "password": data["password"]},
        )
        assert login.status_code == 200, login.text
        fresh.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        assert fresh.get("/api/v1/members/" + member["id"]).json()["name"] == "Alex Member"
        assert fresh.get("/api/v1/invoices/" + invoice["id"]).json()["status"] == "paid"


def test_idempotency_overpayment_refunds(owner, subscription):
    c = owner["client"]
    i = subscription["invoice"]
    idem = str(uuid4())
    p = pay(c, i, "1062.00", idem)
    assert p.status_code == 201, p.text
    assert pay(c, i, "1062.00", idem).json()["id"] == p.json()["id"]
    assert pay(c, i, "100.00", idem).status_code == 409
    assert pay(c, i, "0.01").status_code == 409
    payload = {
        "payment_id": p.json()["id"],
        "amount": "100.00",
        "reason": "Partial return",
        "idempotency_key": str(uuid4()),
    }
    refund = c.post("/api/v1/refunds", json=payload)
    assert refund.status_code == 201, refund.text
    assert c.post("/api/v1/refunds", json=payload).json()["id"] == refund.json()["id"]
    assert c.get("/api/v1/invoices/" + i["id"]).json()["balance"] == "100.00"
    assert c.get("/api/v1/memberships").json()["items"][0]["status"] == "pending_payment"
    payload.update(amount="1000.00", idempotency_key=str(uuid4()))
    assert c.post("/api/v1/refunds", json=payload).status_code == 409
    assert (
        c.post("/api/v1/invoices/" + i["id"] + "/cancel", json={"reason": "Requested cancellation"}).status_code == 409
    )


def test_overlap_renewal_freeze(owner, subscription):
    c = owner["client"]
    s = subscription
    assert c.post("/api/v1/memberships", json=s["payload"]).json()["id"] == s["membership"]["id"]
    duplicate = dict(s["payload"], request_key=str(uuid4()))
    assert c.post("/api/v1/memberships", json=duplicate).status_code == 409
    pay(c, s["invoice"], "1062.00")
    freeze = c.post(
        "/api/v1/memberships/" + s["membership"]["id"] + "/lifecycle",
        json={"action": "freeze", "days": 5, "reason": "Travel break"},
    )
    assert freeze.status_code == 200, freeze.text
    assert freeze.json()["status"] == "frozen"
    assert date.fromisoformat(freeze.json()["end_date"]) - date.fromisoformat(s["membership"]["end_date"]) == timedelta(
        days=5
    )
    data = {"plan_id": s["plan"]["id"], "request_key": str(uuid4())}
    renewed = c.post("/api/v1/memberships/" + s["membership"]["id"] + "/renew", json=data)
    assert renewed.status_code == 201, renewed.text
    assert renewed.json()["start_date"] == freeze.json()["end_date"]
    assert (
        c.post("/api/v1/memberships/" + s["membership"]["id"] + "/renew", json=data).json()["id"]
        == renewed.json()["id"]
    )
    assert (
        c.post(
            "/api/v1/memberships/" + s["membership"]["id"] + "/lifecycle",
            json={"action": "extend", "days": 1, "reason": "Collision test"},
        ).status_code
        == 409
    )


def test_qr_token_one_use(owner, member, subscription):
    c = owner["client"]
    pay(c, subscription["invoice"], "1062.00")
    qr = c.post("/api/v1/attendance/qr/" + member["id"])
    assert qr.status_code == 200, qr.text
    req = {"token": qr.json()["token"], "branch_id": owner["branch"]["id"]}
    entry = c.post("/api/v1/attendance/qr-check-in", json=req)
    assert entry.status_code == 201, entry.text
    c.post("/api/v1/attendance/" + entry.json()["id"] + "/check-out")
    assert c.post("/api/v1/attendance/qr-check-in", json=req).status_code == 400
    assert c.post("/api/v1/attendance/qr-check-in", json={**req, "token": member["id"]}).status_code == 400


def test_cross_tenant_isolation(owner, member, subscription):
    c = owner["client"]
    other = str(uuid4())[:8]
    r = c.post(
        "/api/v1/auth/register",
        json={
            "organization": "Other",
            "slug": "other-" + other,
            "name": "Other Owner",
            "email": other + "@example.com",
            "password": "Strong-test-password-42",
        },
    )
    assert r.status_code == 201, r.text
    c.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    assert c.get("/api/v1/members").json()["total"] == 0
    assert c.get("/api/v1/members/" + member["id"]).status_code == 404
    assert c.patch("/api/v1/members/" + member["id"], json={"name": "Intruder"}).status_code == 404
    assert c.get("/api/v1/invoices/" + subscription["invoice"]["id"]).status_code == 404
    assert (
        c.post(
            "/api/v1/members", json={"branch_id": owner["branch"]["id"], "name": "No", "phone": "999999999"}
        ).status_code
        == 404
    )
    assert c.get("/api/v1/memberships/" + subscription["membership"]["id"] + "/events").status_code == 404


def test_member_search_csv_validation(owner, member):
    c = owner["client"]
    assert c.get("/api/v1/members?q=Alex").json()["total"] == 1
    assert c.get("/api/v1/members?q=missing").json()["total"] == 0
    assert (
        c.post(
            "/api/v1/members", json={"branch_id": owner["branch"]["id"], "name": "Duplicate", "phone": member["phone"]}
        ).status_code
        == 409
    )
    invalid = b"name,phone,email\nNew,9876543210,new@example.com\nBad,xx,not-email\n"
    r = c.post(
        "/api/v1/members/import?branch_id=" + owner["branch"]["id"],
        files={"file": ("members.csv", invalid, "text/csv")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 0 and len(r.json()["errors"]) == 1
    assert c.get("/api/v1/members").json()["total"] == 1
    assert c.get("/api/v1/members?size=1000").status_code == 422


def test_refresh_csrf_rotation_logout(owner):
    c = owner["client"]
    old = c.cookies.get("gymos_refresh")
    csrf = c.cookies.get("gymos_csrf")
    assert c.post("/api/v1/auth/refresh").status_code == 403
    r = c.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    assert c.get("/api/v1/auth/me").status_code == 200
    assert c.cookies.get("gymos_refresh") != old
    # Replay an old refresh token in another request revokes its entire session family.
    r = c.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"gymos_refresh={old}; gymos_csrf={csrf}", "X-CSRF-Token": csrf}
    )
    assert r.status_code == 401, r.text
    assert c.get("/api/v1/auth/me").status_code == 401


def test_receptionist_permissions_and_branch_scope(owner, member):
    c = owner["client"]
    data = {
        "name": "Reception",
        "email": "reception@example.com",
        "role": "Receptionist",
        "branch_ids": [owner["branch"]["id"]],
    }
    invitation = c.post("/api/v1/staff/invite", json=data)
    assert invitation.status_code == 201, invitation.text
    token = parse_qs(urlparse(invitation.json()["activation_url"]).query)["token"][0]
    assert (
        c.post("/api/v1/auth/reset-password", json={"token": token, "password": "Reception-test-password"}).status_code
        == 200
    )
    b = c.post("/api/v1/branches", json={"name": "Restricted", "opens": "00:00", "closes": "00:00"}).json()
    r = c.post(
        "/api/v1/auth/login",
        json={
            "organization": owner["registration"]["slug"],
            "email": data["email"],
            "password": "Reception-test-password",
        },
    )
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    item = c.get("/api/v1/members/" + member["id"])
    assert item.status_code == 200, item.text
    assert "notes" not in item.json() and "emergency_contact" not in item.json()
    assert c.patch("/api/v1/members/" + member["id"], json={"notes": "forbidden"}).status_code == 403
    assert (
        c.post("/api/v1/members", json={"branch_id": b["id"], "name": "Denied", "phone": "9876543210"}).status_code
        == 404
    )
    assert c.get("/api/v1/progress").status_code == 403
    assert c.post("/api/v1/branches", json={"name": "Unauthorized"}).status_code == 403
    assert c.get("/api/v1/staff").status_code == 403


def test_member_portal_is_private(owner, member, subscription):
    c = owner["client"]
    r = c.post(
        "/api/v1/staff/invite",
        json={"name": member["name"], "email": "portal@example.com", "role": "Member", "member_id": member["id"]},
    )
    assert r.status_code == 201, r.text
    token = parse_qs(urlparse(r.json()["activation_url"]).query)["token"][0]
    c.post("/api/v1/auth/reset-password", json={"token": token, "password": "Portal-test-password"})
    r = c.post(
        "/api/v1/auth/login",
        json={
            "organization": owner["registration"]["slug"],
            "email": "portal@example.com",
            "password": "Portal-test-password",
        },
    )
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    portal = c.get("/api/v1/portal")
    assert portal.status_code == 200, portal.text
    assert portal.json()["member"]["id"] == member["id"] and "notes" not in portal.json()["member"]
    assert len(portal.json()["invoices"]) == 1
    assert c.get("/api/v1/members").status_code == 403
    assert c.get("/api/v1/reports/dashboard").status_code == 403


def test_inventory_and_maintenance(owner):
    c = owner["client"]
    b = owner["branch"]["id"]
    r = c.post("/api/v1/inventory", json={"name": "Towels", "sku": "TOWEL", "branch_id": b})
    assert r.status_code == 201, r.text
    item = r.json()
    r = c.post("/api/v1/stock-movements", json={"item_id": item["id"], "quantity": 10, "reason": "Delivery"})
    assert r.status_code == 201, r.text
    assert (
        c.post(
            "/api/v1/stock-movements", json={"item_id": item["id"], "quantity": -11, "reason": "Invalid issue"}
        ).status_code
        == 409
    )
    assert c.get("/api/v1/inventory").json()["items"][0]["stock"] == 10
    eq = c.post(
        "/api/v1/equipment",
        json={"name": "Treadmill", "serial": "EQ-1", "branch_id": b, "next_service": date.today().isoformat()},
    )
    assert eq.status_code == 201, eq.text
    result = c.post(
        "/api/v1/maintenance",
        json={
            "equipment_id": eq.json()["id"],
            "serviced_on": date.today().isoformat(),
            "next_service": (date.today() + timedelta(days=90)).isoformat(),
            "notes": "Belt adjusted",
            "cost": "50.00",
        },
    )
    assert result.status_code == 201, result.text
    assert c.get("/api/v1/expenses").json()["items"][0]["amount"] == "50.00"


def test_training_booking_conflicts(owner, member):
    c = owner["client"]
    t = c.post(
        "/api/v1/trainers",
        json={
            "branch_id": owner["branch"]["id"],
            "name": "Coach",
            "starts": "00:00",
            "ends": "23:59",
            "working_days": list(range(7)),
        },
    )
    assert t.status_code == 201, t.text
    base = {"trainer_id": t.json()["id"], "member_id": member["id"]}
    assert c.post("/api/v1/trainer-assignments", json=base).status_code == 201
    p = c.post("/api/v1/training-packages", json={**base, "name": "Personal training", "sessions": 2})
    assert p.status_code == 201, p.text
    start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    payload = {
        **base,
        "package_id": p.json()["id"],
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=1)).isoformat(),
    }
    r = c.post("/api/v1/training-sessions", json=payload)
    assert r.status_code == 201, r.text
    assert c.post("/api/v1/training-sessions", json=payload).status_code == 409
    assert (
        c.post("/api/v1/training-sessions/" + r.json()["id"] + "/state", json={"state": "completed"}).status_code == 409
    )
    assert (
        c.post("/api/v1/training-sessions/" + r.json()["id"] + "/state", json={"state": "cancelled"}).status_code == 200
    )
    assert c.post("/api/v1/training-sessions", json=payload).status_code == 201
    assert c.get("/api/v1/training-packages").json()["items"][0]["remaining"] == 1


def test_invalid_origin_and_auth(client):
    assert client.get("/api/v1/members").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            headers={"Origin": "https://evil.example"},
            json={"organization": "test", "email": "test@example.com", "password": "none"},
        ).status_code
        == 403
    )


def test_notifications_deduplicate(owner, member, subscription):
    c = owner["client"]
    pay(c, subscription["invoice"], "1062.00")
    c.post("/api/v1/inventory", json={"name": "Empty shelf", "sku": "EMPTY", "branch_id": owner["branch"]["id"]})
    from app.jobs import run_once

    run_once()
    first = c.get("/api/v1/notifications").json()["total"]
    run_once()
    assert c.get("/api/v1/notifications").json()["total"] == first and first >= 1


@pytest.mark.skipif(
    __import__("os").environ.get("TEST_PGLITE") == "1",
    reason="PGlite socket error recovery differs; verify immutable-trigger rollback on native PostgreSQL",
)
def test_schema_and_immutable_records(owner, subscription):
    from app.db import SessionLocal
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    c = owner["client"]
    p = pay(c, subscription["invoice"], "1062.00").json()
    with SessionLocal() as db:
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001"
        with pytest.raises(DBAPIError):
            db.execute(text("UPDATE payments SET amount=1 WHERE id=:id"), {"id": p["id"]})
        db.rollback()
    assert c.get("/health/ready").status_code == 200
