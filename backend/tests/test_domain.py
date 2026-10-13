from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
from app.services.billing import line_total
from app.services.memberships import status
from app.schemas import PlanIn, MemberIn, SessionIn
from pydantic import ValidationError


def test_decimal_rounding():
    assert line_total(3, Decimal("10.01"), Decimal("0.02"), Decimal("18")) == (Decimal("5.40"), Decimal("35.41"))
    assert line_total(1, Decimal("0.05"), Decimal("0"), Decimal("10")) == (Decimal("0.01"), Decimal("0.06"))


def test_membership_boundaries():
    r = SimpleNamespace(
        state="active", start_date=date(2026, 1, 1), end_date=date(2026, 2, 1), frozen_from=None, frozen_until=None
    )
    assert status(r, date(2025, 12, 31)) == "scheduled"
    assert status(r, date(2026, 1, 31)) == "active"
    assert status(r, date(2026, 2, 1)) == "expired"
    assert status(r, date(2026, 2, 1), 2) == "grace"
    assert status(r, date(2026, 2, 3), 2) == "expired"
    r.frozen_from = date(2026, 1, 5)
    r.frozen_until = date(2026, 1, 10)
    assert status(r, date(2026, 1, 9)) == "frozen"
    assert status(r, date(2026, 1, 10)) == "active"
    r.state = "pending"
    assert status(r, date(2026, 1, 10)) == "pending_payment"
    r.state = "cancelled"
    assert status(r, date(2026, 1, 10)) == "cancelled"


def test_plan_validation():
    with pytest.raises(ValidationError):
        PlanIn(name="Bad", duration_days=30, price="10", discount="11")
    with pytest.raises(ValidationError):
        PlanIn(name="Bad", duration_days=0, price="10")


def test_phone_normalization():
    assert MemberIn(branch_id="0" * 36, name="Alex", phone="+91 98765-43210").phone == "+919876543210"
