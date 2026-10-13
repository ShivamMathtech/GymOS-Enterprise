from dataclasses import dataclass
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import (
    User,
    RefreshSession,
    StaffAssignment,
    Role,
    RolePermission,
    Permission,
    Branch,
    Member,
    Trainer,
    TrainerAssignment,
    now,
)
from app.permissions import OWNER_ROLES
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)


@dataclass
class Actor:
    user: User
    permissions: set[str]
    branches: set[str] | None

    @property
    def org_id(self):
        return self.user.org_id

    def need(self, permission):
        if permission not in self.permissions:
            raise HTTPException(403, "Permission denied")

    def branch(self, branch_id):
        if self.branches is not None and branch_id not in self.branches:
            raise HTTPException(404, "Branch not found")


def actor(
    db: Session = Depends(get_db, scope="function"), credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
):
    try:
        if credentials is None:
            raise ValueError()
        payload = decode_token(credentials.credentials)
        if payload["typ"] != "access":
            raise ValueError()
        user = db.scalar(
            select(User).where(User.id == payload["sub"], User.org_id == payload["org"], User.active.is_(True))
        )
        session = db.scalar(
            select(RefreshSession).where(
                RefreshSession.id == payload["sid"],
                RefreshSession.user_id == payload["sub"],
                RefreshSession.org_id == payload["org"],
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > now(),
            )
        )
        if not user or not session:
            raise ValueError()
    except Exception:
        raise HTTPException(401, "Sign in required") from None
    perms = set(
        db.scalars(
            select(Permission.name)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .where(Role.name == user.role)
        )
    )
    branches = (
        None
        if user.role in OWNER_ROLES
        else set(
            db.scalars(
                select(StaffAssignment.branch_id).where(
                    StaffAssignment.org_id == user.org_id, StaffAssignment.user_id == user.id
                )
            )
        )
    )
    if user.role == "Member":
        branches = set(
            db.scalars(select(Member.branch_id).where(Member.org_id == user.org_id, Member.user_id == user.id))
        )
    return Actor(user, perms, branches)


def require(permission):
    def check(a: Actor = Depends(actor)):
        a.need(permission)
        return a

    return check


def owned(db, model, key, a, lock=False):
    q = select(model).where(model.id == key, model.org_id == a.org_id)
    if lock:
        q = q.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(q)
    if not row:
        raise HTTPException(404, "Record not found")
    if model == Branch:
        a.branch(row.id)
    if hasattr(row, "branch_id"):
        a.branch(row.branch_id)
    return row


def member_scope(db, a, q):
    q = q.where(Member.org_id == a.org_id)
    if a.user.role == "Member":
        return q.where(Member.user_id == a.user.id)
    if a.branches is not None:
        q = q.where(Member.branch_id.in_(a.branches))
    if a.user.role == "Trainer":
        assigned = (
            select(TrainerAssignment.member_id)
            .join(Trainer, Trainer.id == TrainerAssignment.trainer_id)
            .where(Trainer.org_id == a.org_id, Trainer.user_id == a.user.id)
        )
        q = q.where(Member.id.in_(assigned))
    return q


def get_member(db, key, a, lock=False):
    q = member_scope(db, a, select(Member).where(Member.id == key))
    if lock:
        q = q.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(q)
    if not row:
        raise HTTPException(404, "Member not found")
    return row


def own_trainer(db, a):
    return db.scalar(select(Trainer).where(Trainer.org_id == a.org_id, Trainer.user_id == a.user.id))
