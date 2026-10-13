from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select, func
from app import models as m, schemas as s
from app.deps import owned, get_member
from app.services.common import audit, local_date, public
from app.services.billing import new_invoice


def status(row, today, grace=0):
    if row.state == "cancelled":
        return "cancelled"
    if row.state == "pending":
        return "pending_payment"
    if today < row.start_date:
        return "scheduled"
    if row.frozen_from and row.frozen_until and row.frozen_from <= today < row.frozen_until:
        return "frozen"
    if today >= row.end_date:
        return "grace" if today < row.end_date + timedelta(days=grace) else "expired"
    return "active"


def dto(db, a, row):
    b = owned(db, m.Branch, row.branch_id, a)
    return dict(
        public(
            row,
            "id created_at member_id plan_id branch_id start_date end_date state all_branches frozen_from frozen_until",
        ),
        status=status(row, local_date(db, a, row.branch_id), b.grace_days),
    )


def check_overlap(db, a, member_id, start, end, except_id=None):
    q = select(m.Membership).where(
        m.Membership.org_id == a.org_id,
        m.Membership.member_id == member_id,
        m.Membership.state != "cancelled",
        m.Membership.start_date < end,
        m.Membership.end_date > start,
    )
    if except_id:
        q = q.where(m.Membership.id != except_id)
    if db.scalar(q):
        raise HTTPException(409, "Membership dates overlap an existing membership")


def assign(db, a, data):
    member = get_member(db, data.member_id, a, lock=True)
    old = db.scalar(
        select(m.Membership).where(m.Membership.org_id == a.org_id, m.Membership.request_key == data.request_key)
    )
    if old:
        if (old.member_id, old.plan_id, old.start_date) != (data.member_id, data.plan_id, data.start_date):
            raise HTTPException(409, "Request key already used with different data")
        return old
    if member.status != "active":
        raise HTTPException(409, "Activate member before assigning a membership")
    plan = owned(db, m.Plan, data.plan_id, a)
    if not plan.active:
        raise HTTPException(409, "Plan is inactive")
    end = data.start_date + timedelta(days=plan.duration_days)
    check_overlap(db, a, member.id, data.start_date, end)
    row = m.Membership(
        org_id=a.org_id,
        member_id=member.id,
        plan_id=plan.id,
        branch_id=member.branch_id,
        start_date=data.start_date,
        end_date=end,
        request_key=data.request_key,
        all_branches=plan.all_branches,
    )
    db.add(row)
    db.flush()
    new_invoice(
        db,
        a,
        member,
        [
            s.InvoiceLineIn(
                description=plan.name, quantity=1, unit_price=plan.price, discount=plan.discount, tax_rate=plan.tax_rate
            )
        ],
        row,
    )
    db.add(m.MembershipEvent(org_id=a.org_id, membership_id=row.id, action="assigned", details={"plan_id": plan.id}))
    audit(db, a, "membership.assign", row.id)
    return row


def renew(db, a, key, data):
    current = owned(db, m.Membership, key, a)
    get_member(db, current.member_id, a, lock=True)
    old = db.scalar(
        select(m.Membership).where(m.Membership.org_id == a.org_id, m.Membership.request_key == data.request_key)
    )
    if old:
        if old.member_id != current.member_id or old.plan_id != data.plan_id:
            raise HTTPException(409, "Request key conflict")
        return old
    latest = db.scalar(
        select(func.max(m.Membership.end_date)).where(
            m.Membership.org_id == a.org_id,
            m.Membership.member_id == current.member_id,
            m.Membership.state != "cancelled",
        )
    )
    start = max(latest or current.end_date, local_date(db, a, current.branch_id))
    row = assign(
        db,
        a,
        s.MembershipIn(
            member_id=current.member_id, plan_id=data.plan_id, start_date=start, request_key=data.request_key
        ),
    )
    db.add(
        m.MembershipEvent(
            org_id=a.org_id,
            membership_id=row.id,
            action="renewed",
            details={"previous_id": current.id, "plan_changed": data.plan_id != current.plan_id},
        )
    )
    return row


def lifecycle(db, a, key, data):
    row = owned(db, m.Membership, key, a)
    get_member(db, row.member_id, a, lock=True)
    row = owned(db, m.Membership, key, a, lock=True)
    today = local_date(db, a, row.branch_id)
    if row.state == "cancelled":
        raise HTTPException(409, "Membership already cancelled")
    if data.action == "cancel":
        row.state = "cancelled"
    else:
        if data.days < 1:
            raise HTTPException(422, "Days must be positive")
        if data.action == "freeze" and status(row, today) != "active":
            raise HTTPException(409, "Only an active membership can be frozen")
        end = row.end_date + timedelta(days=data.days)
        check_overlap(db, a, row.member_id, row.start_date, end, row.id)
        row.end_date = end
        if data.action == "freeze":
            row.frozen_from = today
            row.frozen_until = today + timedelta(days=data.days)
    db.add(
        m.MembershipEvent(
            org_id=a.org_id,
            membership_id=row.id,
            action=data.action,
            details={"days": data.days, "reason": data.reason},
        )
    )
    audit(db, a, "membership." + data.action, row.id, {"days": data.days, "reason": data.reason})
    return row
