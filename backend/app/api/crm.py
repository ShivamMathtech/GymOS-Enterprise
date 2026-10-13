import csv, io, secrets
from pathlib import Path
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from fastapi.responses import Response, FileResponse
from pydantic import ValidationError
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError
from app import models as m, schemas as s
from app.config import settings
from app.db import get_db
from app.deps import Actor, actor, require, owned, get_member, member_scope
from app.services.common import audit, public, page, csv_cell
from app.services.memberships import status
from app.services.common import local_date

router = APIRouter(tags=["Organization & members"])
BRANCH_FIELDS = "id name address timezone opens closes grace_days active"


def member_dto(row, a):
    fields = "id created_at branch_id member_code name status user_id"
    if a.user.role != "Trainer":
        fields += " email phone"
    if "members.private" in a.permissions:
        fields += " emergency_contact notes"
    elif a.user.role == "Member":
        fields += " emergency_contact"
    return dict(public(row, fields), has_photo=bool(row.photo_key))


@router.get("/organization")
def organization(a: Actor = Depends(actor), db: Session = Depends(get_db, scope="function")):
    return public(db.get(m.Organization, a.org_id), "id name slug currency timezone invoice_prefix")


@router.put("/organization")
def update_organization(
    data: s.OrganizationUpdate,
    a: Actor = Depends(require("org.manage")),
    db: Session = Depends(get_db, scope="function"),
):
    row = db.scalar(select(m.Organization).where(m.Organization.id == a.org_id).with_for_update())
    for k, v in data.model_dump().items():
        setattr(row, k, v)
    audit(db, a, "organization.update", row.id)
    return public(row, "id name slug currency timezone invoice_prefix")


@router.get("/branches")
def branches(a: Actor = Depends(actor), db: Session = Depends(get_db, scope="function")):
    q = select(m.Branch).where(m.Branch.org_id == a.org_id)
    if a.branches is not None:
        q = q.where(m.Branch.id.in_(a.branches))
    return [public(r, BRANCH_FIELDS) for r in db.scalars(q.order_by(m.Branch.name))]


@router.post("/branches", status_code=201)
def create_branch(
    data: s.BranchIn, a: Actor = Depends(require("org.manage")), db: Session = Depends(get_db, scope="function")
):
    row = m.Branch(org_id=a.org_id, **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, a, "branch.create", row.id)
    return public(row, BRANCH_FIELDS)


@router.put("/branches/{key}")
def edit_branch(
    key: str,
    data: s.BranchIn,
    a: Actor = Depends(require("org.manage")),
    db: Session = Depends(get_db, scope="function"),
):
    row = owned(db, m.Branch, key, a, lock=True)
    for k, v in data.model_dump().items():
        setattr(row, k, v)
    audit(db, a, "branch.update", row.id)
    return public(row, BRANCH_FIELDS)


@router.get("/members")
def members(
    q: str = Query("", max_length=100),
    branch_id: str | None = None,
    status_filter: str | None = Query(None, alias="status", pattern="^(active|inactive|archived)$"),
    membership_status: str | None = Query(None, pattern="^(active|expired|pending_payment|scheduled|frozen|none)$"),
    page_no: int = Query(1, ge=1, alias="page"),
    size: int = Query(25, ge=1, le=100),
    sort: str = Query("created_at", pattern="^(created_at|name|member_code)$"),
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    a: Actor = Depends(require("members.read")),
    db: Session = Depends(get_db, scope="function"),
):
    stmt = member_scope(db, a, select(m.Member))
    if q:
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(
            or_(m.Member.name.ilike(pattern), m.Member.phone.ilike(pattern), m.Member.member_code.ilike(pattern))
        )
    if branch_id:
        a.branch(branch_id)
        stmt = stmt.where(m.Member.branch_id == branch_id)
    if status_filter:
        stmt = stmt.where(m.Member.status == status_filter)
    if membership_status:
        # Per-branch local date is required; evaluate membership states once then filter IDs.
        visible_ids = member_scope(db, a, select(m.Member.id))
        rows = db.scalars(
            select(m.Membership).where(m.Membership.org_id == a.org_id, m.Membership.member_id.in_(visible_ids))
        ).all()
        states = {}
        for r in rows:
            states.setdefault(r.member_id, set()).add(status(r, local_date(db, a, r.branch_id)))
        match = [
            mid
            for mid, ss in states.items()
            if membership_status in ss and (membership_status != "expired" or "active" not in ss)
        ]
        if membership_status == "none":
            stmt = stmt.where(m.Member.id.not_in(list(states)))
        else:
            stmt = stmt.where(m.Member.id.in_(match))
    rows, total = page(db, stmt, m.Member, page_no, size, sort, direction)
    return {"items": [member_dto(r, a) for r in rows], "total": total, "page": page_no, "size": size}


def insert_member(db, a, data):
    branch = owned(db, m.Branch, data.branch_id, a)
    if not branch.active:
        raise HTTPException(409, "Branch inactive")
    if "members.private" not in a.permissions and (data.notes or data.emergency_contact):
        raise HTTPException(403, "Private member fields require manager permission")
    org = db.scalar(select(m.Organization).where(m.Organization.id == a.org_id).with_for_update())
    if db.scalar(select(m.Member.id).where(m.Member.org_id == a.org_id, m.Member.phone == data.phone)):
        raise HTTPException(409, "A member with this phone already exists")
    org.member_sequence += 1
    row = m.Member(org_id=a.org_id, member_code=f"M-{org.member_sequence:06d}", **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, a, "member.create", row.id)
    return row


@router.post("/members", status_code=201)
def create_member(
    data: s.MemberIn, a: Actor = Depends(require("members.write")), db: Session = Depends(get_db, scope="function")
):
    return member_dto(insert_member(db, a, data), a)


@router.get("/members/export")
def export_members(a: Actor = Depends(require("members.export")), db: Session = Depends(get_db, scope="function")):
    rows = db.scalars(member_scope(db, a, select(m.Member)).order_by(m.Member.member_code).limit(10001)).all()
    if len(rows) > 10000:
        raise HTTPException(422, "Export exceeds 10,000 rows; use the paginated API for a scoped bulk export")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["member_code", "name", "email", "phone", "status"])
    for r in rows:
        writer.writerow([csv_cell(getattr(r, k)) for k in ["member_code", "name", "email", "phone", "status"]])
    audit(db, a, "members.export", a.org_id, {"rows": len(rows)})
    return Response(
        "﻿" + buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=members.csv"}
    )


@router.post("/members/import")
def import_members(
    branch_id: str,
    file: UploadFile = File(...),
    a: Actor = Depends(require("members.write")),
    db: Session = Depends(get_db, scope="function"),
):
    owned(db, m.Branch, branch_id, a)
    raw = file.file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(413, "CSV limit is 2 MB")
    try:
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    except (UnicodeError, csv.Error):
        raise HTTPException(422, "Use a UTF-8 CSV")
    if not rows or len(rows) > 1000:
        raise HTTPException(422, "Upload 1–1,000 rows")
    existing = set(db.scalars(select(m.Member.phone).where(m.Member.org_id == a.org_id)))
    validated = []
    errors = []
    for i, row in enumerate(rows, 2):
        try:
            data = s.MemberIn(
                branch_id=branch_id,
                name=row.get("name", ""),
                phone=row.get("phone", ""),
                email=row.get("email") or None,
            )
            if data.phone in existing:
                raise ValueError("Duplicate phone")
            existing.add(data.phone)
            validated.append(data)
        except (ValidationError, ValueError) as exc:
            message = (
                "; ".join(str(e["loc"][0]) + ": " + e["msg"] for e in exc.errors())
                if isinstance(exc, ValidationError)
                else str(exc)
            )
            errors.append({"row": i, "message": message})
    if errors:
        return {"imported": 0, "errors": errors}
    for data in validated:
        insert_member(db, a, data)
    audit(db, a, "members.import", a.org_id, {"rows": len(validated)})
    return {"imported": len(validated), "errors": []}


@router.get("/members/{key}")
def member(key: str, a: Actor = Depends(require("members.read")), db: Session = Depends(get_db, scope="function")):
    return member_dto(get_member(db, key, a), a)


@router.patch("/members/{key}")
def edit_member(
    key: str,
    data: s.MemberEdit,
    a: Actor = Depends(require("members.write")),
    db: Session = Depends(get_db, scope="function"),
):
    row = get_member(db, key, a, lock=True)
    values = data.model_dump(exclude_unset=True)
    if {"notes", "emergency_contact"} & values.keys() and "members.private" not in a.permissions:
        raise HTTPException(403, "Private fields require manager permission")
    for field in ("name", "phone", "status", "notes", "emergency_contact"):
        if field in values and values[field] is None:
            raise HTTPException(422, f"{field} cannot be null")
    if "phone" in values:
        values["phone"] = s.MemberIn(branch_id=row.branch_id, name=row.name, phone=values["phone"]).phone
    for k, v in values.items():
        setattr(row, k, v)
    audit(db, a, "member.update", row.id, {"fields": list(values)})
    return member_dto(row, a)


@router.post("/members/{key}/photo")
def upload_photo(
    key: str,
    file: UploadFile = File(...),
    a: Actor = Depends(require("members.write")),
    db: Session = Depends(get_db, scope="function"),
):
    row = get_member(db, key, a)
    raw = file.file.read(3_000_001)
    if len(raw) > 3_000_000:
        raise HTTPException(413, "Photo limit is 3 MB")
    try:
        im = Image.open(io.BytesIO(raw))
        if im.format not in {"PNG", "JPEG", "WEBP"} or im.width * im.height > 12_000_000:
            raise ValueError()
        im.load()
        im = im.convert("RGB")
        im.thumbnail((640, 640))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "Upload a valid JPEG, PNG or WebP up to 12 megapixels")
    settings().upload_dir.mkdir(parents=True, exist_ok=True)
    row.photo_key = secrets.token_hex(24) + ".jpg"
    im.save(settings().upload_dir / row.photo_key, "JPEG", quality=85)
    audit(db, a, "member.photo", row.id)
    return member_dto(row, a)


@router.get("/members/{key}/photo")
def photo(key: str, a: Actor = Depends(actor), db: Session = Depends(get_db, scope="function")):
    if not {"members.read", "self.read"} & a.permissions:
        raise HTTPException(403, "Permission denied")
    row = get_member(db, key, a)
    if not row.photo_key or not (settings().upload_dir / row.photo_key).is_file():
        raise HTTPException(404, "Photo not found")
    return FileResponse(
        settings().upload_dir / row.photo_key, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"}
    )
