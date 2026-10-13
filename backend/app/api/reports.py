import csv, io
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app import models as m
from app.db import get_db
from app.deps import Actor, actor, require, member_scope, owned
from app.services.common import page, public, audit, csv_cell
from app.services.memberships import status

router = APIRouter(tags=["Reports & notifications"])


def report_data(db, a, branch_id, start, end):
    org = db.get(m.Organization, a.org_id)
    zone = ZoneInfo(owned(db, m.Branch, branch_id, a).timezone if branch_id else org.timezone)
    today = datetime.now(zone).date()
    start = start or today.replace(day=1)
    end = end or today + timedelta(days=1)
    if end <= start or (end - start).days > 366:
        raise HTTPException(422, "Report range must be 1–366 days; end date is exclusive")
    t0 = datetime.combine(start, time.min, zone)
    t1 = datetime.combine(end, time.min, zone)

    def branch_filter(q, model):
        q = q.where(model.org_id == a.org_id)
        if a.branches is not None:
            q = q.where(model.branch_id.in_(a.branches))
        if branch_id:
            q = q.where(model.branch_id == branch_id)
        return q

    members_q = member_scope(db, a, select(m.Member))
    if branch_id:
        members_q = members_q.where(m.Member.branch_id == branch_id)
    members = db.scalars(members_q).all()
    member_ids = [r.id for r in members]
    memberships = db.scalars(
        select(m.Membership).where(m.Membership.org_id == a.org_id, m.Membership.member_id.in_(member_ids))
    ).all()
    branch_zones = {b.id: ZoneInfo(b.timezone) for b in db.scalars(select(m.Branch).where(m.Branch.org_id == a.org_id))}
    member_day = lambda r: datetime.now(branch_zones[r.branch_id]).date()
    active_ids = {r.member_id for r in memberships if status(r, member_day(r)) == "active"}
    active_ids &= {r.id for r in members if r.status == "active"}
    expired_ids = {r.member_id for r in memberships if status(r, member_day(r)) == "expired"} - active_ids
    invoices = db.scalars(branch_filter(select(m.Invoice), m.Invoice)).all()
    inv_ids = [r.id for r in invoices]
    payment_rows = db.scalars(
        select(m.Payment).where(m.Payment.org_id == a.org_id, m.Payment.invoice_id.in_(inv_ids))
    ).all()
    payment_ids = [r.id for r in payment_rows]
    refund_rows = db.scalars(
        select(m.Refund).where(m.Refund.org_id == a.org_id, m.Refund.payment_id.in_(payment_ids))
    ).all()
    paid = defaultdict(Decimal)
    refunded = defaultdict(Decimal)
    p_invoice = {p.id: p.invoice_id for p in payment_rows}
    for p in payment_rows:
        paid[p.invoice_id] += p.amount
    for r in refund_rows:
        refunded[p_invoice[r.payment_id]] += r.amount
    in_range = lambda v: t0 <= v < t1
    gross = sum((p.amount for p in payment_rows if in_range(p.created_at)), Decimal(0))
    returns = sum((r.amount for r in refund_rows if in_range(r.created_at)), Decimal(0))
    dues = sum(
        (max(Decimal(0), i.total - paid[i.id] + refunded[i.id]) for i in invoices if not i.cancelled_at), Decimal(0)
    )
    attendance = db.scalars(
        branch_filter(select(m.Attendance), m.Attendance).where(
            m.Attendance.checked_in_at >= t0, m.Attendance.checked_in_at < t1
        )
    ).all()
    today_start = datetime.combine(today, time.min, zone)
    today_count = db.scalar(
        branch_filter(select(func.count()).select_from(m.Attendance), m.Attendance).where(
            m.Attendance.checked_in_at >= today_start, m.Attendance.checked_in_at < today_start + timedelta(days=1)
        )
    )
    trend = {
        (start + timedelta(days=n)).isoformat(): {
            "date": (start + timedelta(days=n)).isoformat(),
            "collected": Decimal(0),
            "refunds": Decimal(0),
            "checkins": 0,
        }
        for n in range((end - start).days)
    }
    for p in payment_rows:
        if in_range(p.created_at):
            trend[p.created_at.astimezone(zone).date().isoformat()]["collected"] += p.amount
    for r in refund_rows:
        if in_range(r.created_at):
            trend[r.created_at.astimezone(zone).date().isoformat()]["refunds"] += r.amount
    for row in attendance:
        trend[row.checked_in_at.astimezone(zone).date().isoformat()]["checkins"] += 1
    for v in trend.values():
        v["collected"] = str(v["collected"])
        v["refunds"] = str(v["refunds"])
    branches = db.scalars(select(m.Branch).where(m.Branch.org_id == a.org_id)).all()
    summaries = []
    for b in branches:
        if (a.branches is not None and b.id not in a.branches) or (branch_id and b.id != branch_id):
            continue
        bids = {i.id for i in invoices if i.branch_id == b.id}
        summaries.append(
            {
                "branch_id": b.id,
                "name": b.name,
                "members": sum(r.branch_id == b.id for r in members),
                "collected": str(
                    sum((p.amount for p in payment_rows if p.invoice_id in bids and in_range(p.created_at)), Decimal(0))
                ),
            }
        )
    cohort = {
        r.member_id
        for r in memberships
        if r.state == "active" and r.start_date < start and r.end_date >= start and r.member_id in member_ids
    }
    retained = cohort & active_ids
    low = db.scalar(
        branch_filter(select(func.count()).select_from(m.InventoryItem), m.InventoryItem).where(
            m.InventoryItem.stock <= m.InventoryItem.low_stock_level
        )
    )
    maintenance = db.scalar(
        branch_filter(select(func.count()).select_from(m.Equipment), m.Equipment).where(
            m.Equipment.next_service <= today, m.Equipment.state != "retired"
        )
    )
    trainers = db.scalars(branch_filter(select(m.Trainer), m.Trainer)).all()
    tids = [t.id for t in trainers]
    sessions = db.scalars(
        select(m.TrainingSession).where(
            m.TrainingSession.org_id == a.org_id,
            m.TrainingSession.trainer_id.in_(tids),
            m.TrainingSession.starts_at >= t0,
            m.TrainingSession.starts_at < t1,
        )
    ).all()
    expiries = [
        {
            "member_id": r.member_id,
            "member_name": next((x.name for x in members if x.id == r.member_id), ""),
            "end_date": r.end_date,
            "days_left": (r.end_date - today).days,
        }
        for r in memberships
        if r.state == "active" and today <= r.end_date <= today + timedelta(days=7)
    ]
    expenses = db.scalars(
        branch_filter(select(m.Expense), m.Expense).where(m.Expense.expense_date >= start, m.Expense.expense_date < end)
    ).all()
    return {
        "from_date": start,
        "to_date": end,
        "timezone": str(zone),
        "currency": org.currency,
        "total_members": len(members),
        "active_members": len(active_ids),
        "expired_members": len(expired_ids),
        "new_members": sum(in_range(r.created_at) for r in members),
        "today_attendance": today_count,
        "period_attendance": len(attendance),
        "cash_collected": str(gross),
        "refunds": str(returns),
        "net_cash_collected": str(gross - returns),
        "outstanding": str(dues),
        "invoiced_total": str(
            sum((i.total for i in invoices if not i.cancelled_at and in_range(i.created_at)), Decimal(0))
        ),
        "expenses": str(sum((e.amount for e in expenses), Decimal(0))),
        "retention_pct": round(100 * len(retained) / len(cohort), 1) if cohort else None,
        "churn_pct": round(100 * (len(cohort) - len(retained)) / len(cohort), 1) if cohort else None,
        "retention_cohort": len(cohort),
        "low_stock": low,
        "maintenance_due": maintenance,
        "trend": list(trend.values()),
        "branches": summaries,
        "expiring": expiries,
        "trainer_workload": [
            {
                "name": t.name,
                "sessions": sum(x.trainer_id == t.id for x in sessions),
                "completed": sum(x.trainer_id == t.id and x.state == "completed" for x in sessions),
            }
            for t in trainers
        ],
    }


@router.get("/reports/dashboard")
def dashboard(
    branch_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    a: Actor = Depends(require("reports.read")),
    db: Session = Depends(get_db, scope="function"),
):
    return report_data(db, a, branch_id, from_date, to_date)


@router.get("/reports/export")
def export(
    branch_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    a: Actor = Depends(require("reports.read")),
    db: Session = Depends(get_db, scope="function"),
):
    data = report_data(db, a, branch_id, from_date, to_date)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "cash_collected", "refunds", "checkins", "currency", "timezone"])
    for row in data["trend"]:
        writer.writerow(
            [
                csv_cell(row["date"]),
                row["collected"],
                row["refunds"],
                row["checkins"],
                data["currency"],
                data["timezone"],
            ]
        )
    audit(db, a, "report.export", a.org_id, {"from": str(data["from_date"]), "to": str(data["to_date"])})
    return Response(
        buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=gymos-report.csv"}
    )


@router.get("/audit")
def logs(
    action: str = Query("", max_length=80),
    page_no: int = Query(1, ge=1, alias="page"),
    size: int = Query(25, ge=1, le=100),
    a: Actor = Depends(require("audit.read")),
    db: Session = Depends(get_db, scope="function"),
):
    # Security audit is organization-wide; limited-branch managers receive their own actions only.
    q = select(m.AuditLog).where(m.AuditLog.org_id == a.org_id)
    if a.branches is not None:
        q = q.where(m.AuditLog.actor_id == a.user.id)
    if action:
        q = q.where(m.AuditLog.action.ilike("%" + action + "%"))
    rows, total = page(db, q, m.AuditLog, page_no, size)
    return {
        "items": [public(r, "id created_at actor_id action entity_id details") for r in rows],
        "total": total,
        "page": page_no,
        "size": size,
    }


@router.get("/notifications")
def notifications(
    page_no: int = Query(1, ge=1, alias="page"),
    size: int = Query(25, ge=1, le=100),
    a: Actor = Depends(actor),
    db: Session = Depends(get_db, scope="function"),
):
    rows, total = page(
        db,
        select(m.Notification).where(m.Notification.org_id == a.org_id, m.Notification.user_id == a.user.id),
        m.Notification,
        page_no,
        size,
    )
    return {
        "items": [public(r, "id created_at title body read_at") for r in rows],
        "total": total,
        "page": page_no,
        "size": size,
    }


@router.post("/notifications/{key}/read")
def mark_read(key: str, a: Actor = Depends(actor), db: Session = Depends(get_db, scope="function")):
    row = db.scalar(
        select(m.Notification).where(
            m.Notification.org_id == a.org_id, m.Notification.user_id == a.user.id, m.Notification.id == key
        )
    )
    if not row:
        raise HTTPException(404, "Notification not found")
    row.read_at = m.now()
    return {"message": "Read"}
