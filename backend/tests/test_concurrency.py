import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.concurrency,
    pytest.mark.skipif(
        os.environ.get("TEST_PGLITE") == "1", reason="Native PostgreSQL required for true concurrent transactions"
    ),
]


def test_simultaneous_duplicate_payments(owner, subscription):
    from fastapi.testclient import TestClient
    from app.main import app

    gate = Barrier(2)
    token = owner["client"].headers["Authorization"]
    payload = {
        "invoice_id": subscription["invoice"]["id"],
        "amount": "1062.00",
        "method": "cash",
        "idempotency_key": str(uuid4()),
    }

    def worker():
        with TestClient(app) as c:
            c.headers["Authorization"] = token
            gate.wait(timeout=10)
            r = c.post("/api/v1/payments", json=payload)
            return r.status_code, r.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(), range(2)))
    assert [r[0] for r in results] == [201, 201], results
    assert results[0][1]["id"] == results[1][1]["id"]
    invoice = owner["client"].get("/api/v1/invoices/" + subscription["invoice"]["id"]).json()
    assert invoice["net_paid"] == "1062.00"


def test_simultaneous_checkins(owner, member, subscription):
    from fastapi.testclient import TestClient
    from app.main import app

    c = owner["client"]
    c.post(
        "/api/v1/payments",
        json={
            "invoice_id": subscription["invoice"]["id"],
            "amount": "1062.00",
            "method": "cash",
            "idempotency_key": str(uuid4()),
        },
    )
    gate = Barrier(2)
    token = c.headers["Authorization"]
    payload = {"member_id": member["id"], "branch_id": owner["branch"]["id"]}

    def worker():
        with TestClient(app) as client:
            client.headers["Authorization"] = token
            gate.wait(timeout=10)
            return client.post("/api/v1/attendance/check-in", json=payload).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(), range(2)))
    assert sorted(results) == [201, 409]
