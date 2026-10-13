from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from app import models as m, schemas as s
from app.db import get_db
from app.deps import Actor, require, owned, get_member
from app.api.resources import filter_resource
from app.services.common import public, page, audit

router = APIRouter(tags=["Training sessions & stock control"])
SESSION_FIELDS = "id created_at trainer_id member_id package_id starts_at ends_at state"


def book(db, a, data, existing=None):
    trainer = owned(db, m.Trainer, data.trainer_id, a, lock=True)
    member = get_member(db, data.member_id, a, lock=True)
    if a.user.role == "Trainer" and trainer.user_id != a.user.id:
        raise HTTPException(403, "Only your own schedule is available")
    if not trainer.active or member.status != "active":
        raise HTTPException(409, "Trainer or member inactive")
    if data.starts_at <= m.now():
        raise HTTPException(422, "Book a future session")
    package = owned(db, m.TrainingPackage, data.package_id, a, lock=True)
    if (package.member_id, package.trainer_id) != (member.id, trainer.id):
        raise HTTPException(422, "Package does not belong to this member and trainer")
    branch = owned(db, m.Branch, trainer.branch_id, a)
    start = data.starts_at.astimezone(ZoneInfo(branch.timezone))
    end = data.ends_at.astimezone(ZoneInfo(branch.timezone))
    if (
        start.date() != end.date()
        or start.weekday() not in trainer.working_days
        or start.strftime("%H:%M") < trainer.starts
        or end.strftime("%H:%M") > trainer.ends
    ):
        raise HTTPException(409, "Outside trainer availability")
    conflicts = select(m.TrainingSession).where(
        m.TrainingSession.org_id == a.org_id,
        m.TrainingSession.state == "booked",
        or_(m.TrainingSession.trainer_id == trainer.id, m.TrainingSession.member_id == member.id),
        m.TrainingSession.starts_at < data.ends_at,
        m.TrainingSession.ends_at > data.starts_at,
    )
    usage = (
        select(func.count())
        .select_from(m.TrainingSession)
        .where(
            m.TrainingSession.org_id == a.org_id,
            m.TrainingSession.package_id == package.id,
            m.TrainingSession.state != "cancelled",
        )
    )
    if existing:
        conflicts = conflicts.where(m.TrainingSession.id != existing.id)
        usage = usage.where(m.TrainingSession.id != existing.id)
    if db.scalar(conflicts):
        raise HTTPException(409, "Trainer or member already booked at this time")
    if db.scalar(usage) >= package.sessions:
        raise HTTPException(409, "No sessions remaining in this package")
    if existing:
        if existing.state != "booked":
            raise HTTPException(409, "Only booked sessions can be rescheduled")
        if (existing.trainer_id, existing.member_id, existing.package_id) != (
            data.trainer_id,
            data.member_id,
            data.package_id,
        ):
            raise HTTPException(409, "Reschedule keeps the same trainer, member and package")
        existing.starts_at = data.starts_at
        existing.ends_at = data.ends_at
        row = existing
    else:
        row = m.TrainingSession(org_id=a.org_id, **data.model_dump())
        db.add(row)
    db.flush()
    audit(db, a, "session.reschedule" if existing else "session.book", row.id)
    return public(row, SESSION_FIELDS)


@router.get("/training-sessions")
def sessions(
    trainer_id: str | None = None,
    member_id: str | None = None,
    page_no: int = Query(1, ge=1, alias="page"),
    size: int = Query(25, ge=1, le=100),
    a: Actor = Depends(require("training.read")),
    db: Session = Depends(get_db, scope="function"),
):
    q = filter_resource(db, a, m.TrainingSession, select(m.TrainingSession))
    if trainer_id:
        q = q.where(m.TrainingSession.trainer_id == trainer_id)
    if member_id:
        q = q.where(m.TrainingSession.member_id == member_id)
    rows, total = page(db, q, m.TrainingSession, page_no, size, "starts_at", "asc")
    return {"items": [public(r, SESSION_FIELDS) for r in rows], "total": total, "page": page_no, "size": size}


@router.post("/training-sessions", status_code=201)
def create_session(
    data: s.SessionIn, a: Actor = Depends(require("training.write")), db: Session = Depends(get_db, scope="function")
):
    return book(db, a, data)


@router.put("/training-sessions/{key}")
def reschedule(
    key: str,
    data: s.SessionIn,
    a: Actor = Depends(require("training.write")),
    db: Session = Depends(get_db, scope="function"),
):
    row = db.scalar(
        filter_resource(db, a, m.TrainingSession, select(m.TrainingSession).where(m.TrainingSession.id == key))
    )
    if not row:
        raise HTTPException(404, "Session not found")
    # book acquires a trainer lock before all mutable scheduling reads.
    owned(db, m.Trainer, row.trainer_id, a, lock=True)
    db.refresh(row)
    return book(db, a, data, row)


@router.post("/training-sessions/{key}/state")
def session_state(
    key: str,
    data: s.SessionState,
    a: Actor = Depends(require("training.write")),
    db: Session = Depends(get_db, scope="function"),
):
    row = db.scalar(
        filter_resource(db, a, m.TrainingSession, select(m.TrainingSession).where(m.TrainingSession.id == key))
    )
    if not row:
        raise HTTPException(404, "Session not found")
    owned(db, m.Trainer, row.trainer_id, a, lock=True)
    db.refresh(row)
    if row.state != "booked":
        raise HTTPException(409, "Session is already closed")
    if data.state != "cancelled" and row.ends_at > m.now():
        raise HTTPException(409, "Complete attendance after the session ends")
    row.state = data.state
    audit(db, a, "session." + data.state, row.id)
    return public(row, SESSION_FIELDS)


@router.post("/stock-movements", status_code=201)
def move_stock(
    data: s.StockIn, a: Actor = Depends(require("inventory.write")), db: Session = Depends(get_db, scope="function")
):
    item = owned(db, m.InventoryItem, data.item_id, a, lock=True)
    if data.quantity == 0 or item.stock + data.quantity < 0:
        raise HTTPException(409, "Movement must be nonzero and cannot make stock negative")
    item.stock += data.quantity
    row = m.StockMovement(org_id=a.org_id, **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, a, "stock.move", row.id, {"quantity": row.quantity, "reason": row.reason})
    return public(row, "id created_at item_id quantity reason")


@router.get("/stock-movements")
def movements(
    item_id: str,
    page_no: int = Query(1, ge=1, alias="page"),
    size: int = Query(25, ge=1, le=100),
    a: Actor = Depends(require("inventory.read")),
    db: Session = Depends(get_db, scope="function"),
):
    owned(db, m.InventoryItem, item_id, a)
    rows, total = page(
        db,
        select(m.StockMovement).where(m.StockMovement.org_id == a.org_id, m.StockMovement.item_id == item_id),
        m.StockMovement,
        page_no,
        size,
    )
    return {
        "items": [public(r, "id created_at item_id quantity reason") for r in rows],
        "total": total,
        "page": page_no,
        "size": size,
    }


@router.post("/maintenance", status_code=201)
def maintenance(
    data: s.MaintenanceIn,
    a: Actor = Depends(require("inventory.write")),
    db: Session = Depends(get_db, scope="function"),
):
    item = owned(db, m.Equipment, data.equipment_id, a, lock=True)
    if data.next_service <= data.serviced_on:
        raise HTTPException(422, "Next service must follow service date")
    expense = None
    if data.cost > 0:
        a.need("finance.write")
        expense = m.Expense(
            org_id=a.org_id,
            branch_id=item.branch_id,
            category="Equipment maintenance",
            description=item.name + " service",
            amount=data.cost,
            expense_date=data.serviced_on,
        )
        db.add(expense)
        db.flush()
    row = m.Maintenance(
        org_id=a.org_id,
        equipment_id=item.id,
        expense_id=expense.id if expense else None,
        serviced_on=data.serviced_on,
        notes=data.notes,
        cost=data.cost,
    )
    db.add(row)
    item.next_service = data.next_service
    item.state = "operational"
    db.flush()
    audit(db, a, "equipment.service", row.id)
    return public(row, "id equipment_id expense_id serviced_on notes cost")


@router.get("/maintenance")
def maintenance_history(
    equipment_id: str,
    page_no: int = Query(1, ge=1, alias="page"),
    size: int = Query(25, ge=1, le=100),
    a: Actor = Depends(require("inventory.read")),
    db: Session = Depends(get_db, scope="function"),
):
    owned(db, m.Equipment, equipment_id, a)
    rows, total = page(
        db,
        select(m.Maintenance).where(m.Maintenance.org_id == a.org_id, m.Maintenance.equipment_id == equipment_id),
        m.Maintenance,
        page_no,
        size,
    )
    return {
        "items": [public(r, "id equipment_id expense_id serviced_on notes cost") for r in rows],
        "total": total,
        "page": page_no,
        "size": size,
    }


@router.get("/trainer-accounts")
def trainer_accounts(a: Actor = Depends(require("training.read")), db: Session = Depends(get_db, scope="function")):
    q = select(m.User).where(m.User.org_id == a.org_id, m.User.role == "Trainer", m.User.active.is_(True))
    if a.branches is not None:
        ids = select(m.StaffAssignment.user_id).where(
            m.StaffAssignment.org_id == a.org_id, m.StaffAssignment.branch_id.in_(a.branches)
        )
        q = q.where(m.User.id.in_(ids))
    if a.user.role == "Trainer":
        q = q.where(m.User.id == a.user.id)
    return [public(r, "id name") for r in db.scalars(q.order_by(m.User.name))]
