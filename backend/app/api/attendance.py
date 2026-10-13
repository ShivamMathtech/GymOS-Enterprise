import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models as m, schemas as s
from app.db import get_db
from app.deps import Actor, actor, require, owned, get_member, member_scope
from app.security import digest
from app.services.common import audit, public, page, local_date
from app.services.memberships import status

router = APIRouter(prefix="/attendance", tags=["Attendance"])
FIELDS = "id member_id branch_id checked_in_at checked_out_at source"


def checkin(db, a, member_id, branch_id, source="manual"):
    member = get_member(db, member_id, a, lock=True)
    branch = owned(db, m.Branch, branch_id, a)
    if not branch.active or member.status != "active":
        raise HTTPException(409, "Member or branch inactive")
    time = datetime.now(ZoneInfo(branch.timezone)).strftime("%H:%M")
    allowed = (
        (branch.opens <= time < branch.closes)
        if branch.opens < branch.closes
        else (time >= branch.opens or time < branch.closes)
    )
    if branch.opens == branch.closes:
        allowed = True
    if not allowed:
        raise HTTPException(409, "Branch is outside its working hours")
    rows = db.scalars(
        select(m.Membership).where(m.Membership.org_id == a.org_id, m.Membership.member_id == member.id)
    ).all()
    if not any(
        (r.branch_id == branch.id or r.all_branches)
        and status(r, local_date(db, a, branch.id), branch.grace_days) in {"active", "grace"}
        for r in rows
    ):
        raise HTTPException(409, "No paid, eligible membership for this branch")
    if db.scalar(
        select(m.Attendance).where(
            m.Attendance.org_id == a.org_id, m.Attendance.member_id == member.id, m.Attendance.checked_out_at.is_(None)
        )
    ):
        raise HTTPException(409, "Member is already checked in")
    row = m.Attendance(org_id=a.org_id, member_id=member.id, branch_id=branch.id, source=source)
    db.add(row)
    db.flush()
    audit(db, a, "attendance.checkin", row.id)
    return public(row, FIELDS)


@router.get("")
def attendance(
    member_id: str | None = None,
    branch_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page_no: int = Query(1, ge=1, alias="page"),
    size: int = Query(25, ge=1, le=100),
    a: Actor = Depends(require("attendance.read")),
    db: Session = Depends(get_db, scope="function"),
):
    q = select(m.Attendance).where(
        m.Attendance.org_id == a.org_id, m.Attendance.member_id.in_(member_scope(db, a, select(m.Member.id)))
    )
    if a.branches is not None:
        q = q.where(m.Attendance.branch_id.in_(a.branches))
    if member_id:
        get_member(db, member_id, a)
        q = q.where(m.Attendance.member_id == member_id)
    if branch_id:
        a.branch(branch_id)
        q = q.where(m.Attendance.branch_id == branch_id)
    if from_date:
        q = q.where(m.Attendance.checked_in_at >= from_date)
    if to_date:
        q = q.where(m.Attendance.checked_in_at < to_date)
    rows, total = page(db, q, m.Attendance, page_no, size)
    return {"items": [public(r, FIELDS) for r in rows], "total": total, "page": page_no, "size": size}


@router.post("/check-in", status_code=201)
def manual(
    data: s.CheckIn, a: Actor = Depends(require("attendance.write")), db: Session = Depends(get_db, scope="function")
):
    return checkin(db, a, data.member_id, data.branch_id)


@router.post("/{key}/check-out")
def checkout(
    key: str, a: Actor = Depends(require("attendance.write")), db: Session = Depends(get_db, scope="function")
):
    row = owned(db, m.Attendance, key, a, lock=True)
    if row.checked_out_at:
        raise HTTPException(409, "Already checked out")
    row.checked_out_at = m.now()
    audit(db, a, "attendance.checkout", row.id)
    return public(row, FIELDS)


@router.post("/qr/{member_id}")
def qr(member_id: str, a: Actor = Depends(actor), db: Session = Depends(get_db, scope="function")):
    if not {"attendance.write", "self.read"} & a.permissions:
        raise HTTPException(403, "Permission denied")
    get_member(db, member_id, a)
    token = secrets.token_urlsafe(40)
    expiry = m.now() + timedelta(minutes=2)
    db.add(m.QRToken(org_id=a.org_id, member_id=member_id, token_hash=digest(token), expires_at=expiry))
    return {"token": token, "expires_at": expiry}


@router.post("/qr-check-in", status_code=201)
def qr_checkin(
    data: s.QRCheckIn, a: Actor = Depends(require("attendance.write")), db: Session = Depends(get_db, scope="function")
):
    token = db.scalar(
        select(m.QRToken)
        .where(m.QRToken.org_id == a.org_id, m.QRToken.token_hash == digest(data.token))
        .with_for_update()
    )
    if not token or token.consumed_at or token.expires_at <= m.now():
        raise HTTPException(400, "QR code is invalid, expired or already used")
    result = checkin(db, a, token.member_id, data.branch_id, "qr")
    token.consumed_at = m.now()
    return result


@router.patch("/{key}")
def correction(
    key: str,
    data: s.Correction,
    a: Actor = Depends(require("attendance.correct")),
    db: Session = Depends(get_db, scope="function"),
):
    row = owned(db, m.Attendance, key, a, lock=True)
    if data.checked_in_at > m.now() or (data.checked_out_at and data.checked_out_at > m.now()):
        raise HTTPException(422, "Attendance cannot be in the future")
    row.checked_in_at = data.checked_in_at
    row.checked_out_at = data.checked_out_at
    audit(db, a, "attendance.correct", key, {"reason": data.reason})
    return public(row, FIELDS)
