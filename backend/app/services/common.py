from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, func
from app.models import AuditLog, Branch, Organization


def audit(db, a, action, entity_id, details=None):
    db.add(AuditLog(org_id=a.org_id, actor_id=a.user.id, action=action, entity_id=entity_id, details=details or {}))


def local_date(db, a, branch_id=None):
    if branch_id:
        b = db.scalar(select(Branch).where(Branch.id == branch_id, Branch.org_id == a.org_id))
        if not b:
            raise HTTPException(404, "Branch not found")
        zone = b.timezone
    else:
        zone = db.get(Organization, a.org_id).timezone
    return datetime.now(ZoneInfo(zone)).date()


def public(row, fields):
    # Explicit field whitelist is the DTO boundary. Never serialize __dict__.
    return {
        k: (str(getattr(row, k)) if isinstance(getattr(row, k), Decimal) else getattr(row, k)) for k in fields.split()
    }


def page(db, q, model, page, size, sort="created_at", direction="desc"):
    total = db.scalar(select(func.count()).select_from(q.order_by(None).subquery()))
    col = getattr(model, sort)
    rows = db.scalars(
        q.order_by(col.desc() if direction == "desc" else col.asc(), model.id).offset((page - 1) * size).limit(size)
    ).all()
    return rows, total


def csv_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text
