import secrets, hmac, smtplib
from email.message import EmailMessage
from datetime import timedelta
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from app import models as m, schemas as s
from app.config import settings
from app.db import get_db, SessionLocal
from app.deps import actor, require, Actor, owned
from app.permissions import OWNER_ROLES
from app.security import hash_password, verify_password, digest, access_token, DUMMY_HASH
from app.services.common import audit, public

router = APIRouter(prefix="/auth", tags=["Authentication"])
USER_FIELDS = "id name email role active created_at"


def rate_limit(request, identity=""):
    cfg = settings()
    key = digest((request.client.host if request.client else "unknown") + request.url.path + identity.lower())
    # Independent committed transaction also counts rejected attempts, across workers.
    with SessionLocal.begin() as db:
        stmt = (
            insert(m.RateBucket)
            .values(key=key, count=1, expires_at=m.now() + timedelta(minutes=15))
            .on_conflict_do_nothing()
        )
        db.execute(stmt)
        row = db.scalar(select(m.RateBucket).where(m.RateBucket.key == key).with_for_update())
        if row.expires_at <= m.now():
            row.count = 0
            row.expires_at = m.now() + timedelta(minutes=15)
        row.count += 1
        count = row.count
    if count > cfg.auth_rate_limit:
        raise HTTPException(429, "Too many attempts; try again in 15 minutes")


def session_response(db, user, response, request, family_id=None):
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    row = m.RefreshSession(
        org_id=user.org_id,
        user_id=user.id,
        family_id=family_id or m.uid(),
        token_hash=digest(token),
        csrf_hash=digest(csrf),
        expires_at=m.now() + timedelta(days=settings().refresh_days),
        device=request.headers.get("user-agent", "API")[:200],
    )
    db.add(row)
    db.flush()
    response.set_cookie(
        "gymos_refresh",
        token,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
        max_age=settings().refresh_days * 86400,
    )
    response.set_cookie(
        "gymos_csrf",
        csrf,
        httponly=False,
        secure=settings().cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings().refresh_days * 86400,
    )
    return {"access_token": access_token(user, row.id), "token_type": "bearer", "user": public(user, USER_FIELDS)}


def refresh_record(db, request):
    token = request.cookies.get("gymos_refresh", "")
    csrf = request.headers.get("x-csrf-token", "")
    if not token or not csrf or not hmac.compare_digest(csrf, request.cookies.get("gymos_csrf", "")):
        raise HTTPException(403, "CSRF validation failed")
    row = db.scalar(select(m.RefreshSession).where(m.RefreshSession.token_hash == digest(token)).with_for_update())
    if not row or not hmac.compare_digest(row.csrf_hash, digest(csrf)):
        raise HTTPException(401, "Session expired")
    return row


@router.post("/register", status_code=201)
def register(data: s.Register, request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    if not settings().allow_registration:
        raise HTTPException(403, "Registration disabled")
    rate_limit(request)
    org = m.Organization(name=data.organization, slug=data.slug, timezone=data.timezone)
    db.add(org)
    db.flush()
    user = m.User(
        org_id=org.id,
        name=data.name,
        email=str(data.email).lower(),
        password_hash=hash_password(data.password),
        role="Gym Owner",
    )
    db.add(user)
    db.flush()
    db.add(m.AuditLog(org_id=org.id, actor_id=user.id, action="organization.register", entity_id=org.id))
    return session_response(db, user, response, request)


@router.post("/login")
def login(data: s.Login, request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    rate_limit(request)
    org = db.scalar(select(m.Organization).where(m.Organization.slug == data.organization.lower()))
    user = (
        db.scalar(select(m.User).where(m.User.org_id == org.id, m.User.email == str(data.email).lower()))
        if org
        else None
    )
    valid = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid or not user.active:
        raise HTTPException(401, "Invalid organization, email or password")
    db.add(m.AuditLog(org_id=user.org_id, actor_id=user.id, action="auth.login", entity_id=user.id))
    return session_response(db, user, response, request)


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    row = refresh_record(db, request)
    if row.revoked_at is not None:
        db.execute(
            update(m.RefreshSession).where(m.RefreshSession.family_id == row.family_id).values(revoked_at=m.now())
        )
        db.commit()  # Replay revocation must survive the rejected response.
        raise HTTPException(401, "Refresh replay detected; sign in again")
    if row.expires_at <= m.now():
        raise HTTPException(401, "Session expired")
    user = db.scalar(
        select(m.User).where(m.User.id == row.user_id, m.User.org_id == row.org_id, m.User.active.is_(True))
    )
    if not user:
        raise HTTPException(401, "Account unavailable")
    row.revoked_at = m.now()
    return session_response(db, user, response, request, row.family_id)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    row = refresh_record(db, request)
    db.execute(update(m.RefreshSession).where(m.RefreshSession.family_id == row.family_id).values(revoked_at=m.now()))
    response.delete_cookie("gymos_refresh", path="/api/v1/auth")
    response.delete_cookie("gymos_csrf", path="/")
    return {"message": "Signed out"}


@router.get("/me")
def me(a: Actor = Depends(actor), db: Session = Depends(get_db, scope="function")):
    org = db.get(m.Organization, a.org_id)
    return {
        "user": public(a.user, USER_FIELDS),
        "permissions": sorted(a.permissions),
        "branch_ids": sorted(a.branches) if a.branches is not None else None,
        "organization": public(org, "id name slug currency timezone invoice_prefix"),
    }


@router.get("/sessions")
def sessions(a: Actor = Depends(actor), db: Session = Depends(get_db, scope="function")):
    rows = db.scalars(
        select(m.RefreshSession).where(
            m.RefreshSession.org_id == a.org_id,
            m.RefreshSession.user_id == a.user.id,
            m.RefreshSession.revoked_at.is_(None),
            m.RefreshSession.expires_at > m.now(),
        )
    )
    return [public(r, "id device created_at expires_at") for r in rows]


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: str, a: Actor = Depends(actor), db: Session = Depends(get_db, scope="function")):
    row = db.scalar(
        select(m.RefreshSession).where(
            m.RefreshSession.id == session_id,
            m.RefreshSession.org_id == a.org_id,
            m.RefreshSession.user_id == a.user.id,
        )
    )
    if not row:
        raise HTTPException(404, "Session not found")
    db.execute(update(m.RefreshSession).where(m.RefreshSession.family_id == row.family_id).values(revoked_at=m.now()))
    audit(db, a, "auth.revoke", row.id)
    return {"message": "Session revoked"}


def issue_action(db, user, kind):
    token = secrets.token_urlsafe(48)
    db.add(
        m.ActionToken(
            org_id=user.org_id,
            user_id=user.id,
            kind=kind,
            token_hash=digest(token),
            expires_at=m.now() + timedelta(hours=1 if kind == "reset" else 48),
        )
    )
    return settings().frontend_url + "/activate?" + urlencode({"token": token, "kind": kind})


def email_action(email, url, kind):
    cfg = settings()
    if not cfg.smtp_host:
        return False
    msg = EmailMessage()
    msg["Subject"] = "GymOS account " + kind
    msg["From"] = cfg.smtp_from
    msg["To"] = email
    msg.set_content("Use this one-time link to " + kind + " your GymOS account: " + url)
    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as smtp:
            if cfg.smtp_starttls:
                smtp.starttls()
            if cfg.smtp_username:
                smtp.login(cfg.smtp_username, cfg.smtp_password)
            smtp.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException):
        return False


@router.post("/forgot-password")
def forgot(data: s.Forgot, request: Request, db: Session = Depends(get_db, scope="function")):
    rate_limit(request)
    org = db.scalar(select(m.Organization).where(m.Organization.slug == data.organization.lower()))
    user = (
        db.scalar(
            select(m.User).where(
                m.User.org_id == org.id, m.User.email == str(data.email).lower(), m.User.active.is_(True)
            )
        )
        if org
        else None
    )
    if user:
        url = issue_action(db, user, "reset")
        db.flush()
        if not email_action(user.email, url, "reset") and settings().app_env == "development":
            # Never expose a reset token through an unauthenticated endpoint or logs.
            from pathlib import Path
            import os

            path = Path("var/dev-outbox")
            path.mkdir(parents=True, exist_ok=True)
            dest = path / (m.uid() + ".txt")
            fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(url)
    return {
        "message": "If that account is active, reset instructions have been sent. Local developers can check backend/var/dev-outbox."
    }


@router.post("/reset-password")
def reset_password(data: s.Reset, request: Request, db: Session = Depends(get_db, scope="function")):
    rate_limit(request)
    token = db.scalar(select(m.ActionToken).where(m.ActionToken.token_hash == digest(data.token)).with_for_update())
    if not token or token.used_at or token.expires_at <= m.now():
        raise HTTPException(400, "Invalid or expired link")
    user = db.scalar(select(m.User).where(m.User.id == token.user_id, m.User.org_id == token.org_id).with_for_update())
    if token.kind == "reset" and not user.active:
        raise HTTPException(400, "Account disabled")
    user.password_hash = hash_password(data.password)
    if token.kind == "invite":
        user.active = True
    token.used_at = m.now()
    db.execute(
        update(m.ActionToken)
        .where(m.ActionToken.user_id == user.id, m.ActionToken.org_id == user.org_id)
        .values(used_at=m.now())
    )
    db.execute(update(m.RefreshSession).where(m.RefreshSession.user_id == user.id).values(revoked_at=m.now()))
    db.add(m.AuditLog(org_id=user.org_id, actor_id=user.id, action="auth." + token.kind, entity_id=user.id))
    return {"message": "Password saved. Sign in with your organization ID."}


staff = APIRouter(prefix="/staff", tags=["Staff"])


@staff.get("")
def list_staff(a: Actor = Depends(require("staff.manage")), db: Session = Depends(get_db, scope="function")):
    rows = db.scalars(select(m.User).where(m.User.org_id == a.org_id).order_by(m.User.name))
    return [
        dict(
            public(r, USER_FIELDS),
            branch_ids=list(
                db.scalars(
                    select(m.StaffAssignment.branch_id).where(
                        m.StaffAssignment.user_id == r.id, m.StaffAssignment.org_id == a.org_id
                    )
                )
            ),
        )
        for r in rows
    ]


@staff.post("/invite", status_code=201)
def invite(
    data: s.Invite, a: Actor = Depends(require("staff.manage")), db: Session = Depends(get_db, scope="function")
):
    if data.role != "Gym Owner" and not data.branch_ids and data.role != "Member":
        raise HTTPException(422, "Assign at least one branch")
    for bid in data.branch_ids:
        owned(db, m.Branch, bid, a)
    if data.role == "Member" and not data.member_id:
        raise HTTPException(422, "A member profile is required")
    if data.member_id and data.role != "Member":
        raise HTTPException(422, "Only Member accounts can link a member profile")
    member = owned(db, m.Member, data.member_id, a, lock=True) if data.member_id else None
    if member and member.user_id:
        raise HTTPException(409, "Member already has an account")
    user = m.User(
        org_id=a.org_id,
        name=data.name,
        email=str(data.email).lower(),
        role=data.role,
        active=False,
        password_hash=hash_password(secrets.token_urlsafe(48)),
    )
    db.add(user)
    db.flush()
    for bid in set(data.branch_ids):
        db.add(m.StaffAssignment(org_id=a.org_id, user_id=user.id, branch_id=bid))
    if member:
        member.user_id = user.id
    url = issue_action(db, user, "invite")
    audit(db, a, "staff.invite", user.id, {"role": user.role})
    delivered = email_action(user.email, url, "activate")
    return {
        "user": public(user, USER_FIELDS),
        "email_delivered": delivered,
        "activation_url": url if not delivered else None,
    }


@staff.put("/{user_id}")
def edit_staff(
    user_id: str,
    data: s.StaffUpdate,
    a: Actor = Depends(require("staff.manage")),
    db: Session = Depends(get_db, scope="function"),
):
    # Serialize ownership changes so concurrent updates cannot remove every owner.
    db.scalar(select(m.Organization).where(m.Organization.id == a.org_id).with_for_update())
    user = owned(db, m.User, user_id, a, lock=True)
    if user.id == a.user.id:
        raise HTTPException(409, "Use another owner account to change your own access")
    if data.role == "Member" or user.role == "Member":
        raise HTTPException(
            409,
            "Member role changes require unlinking through an administrator migration; use activation/deactivation separately",
        )
    if not data.branch_ids and data.role not in OWNER_ROLES:
        raise HTTPException(422, "Assign at least one branch")
    for bid in data.branch_ids:
        owned(db, m.Branch, bid, a)
    user.role = data.role
    user.active = data.active
    if not data.active:
        db.execute(
            update(m.ActionToken)
            .where(m.ActionToken.user_id == user.id, m.ActionToken.org_id == a.org_id)
            .values(used_at=m.now())
        )
    db.execute(
        delete(m.StaffAssignment).where(m.StaffAssignment.user_id == user.id, m.StaffAssignment.org_id == a.org_id)
    )
    for bid in set(data.branch_ids):
        db.add(m.StaffAssignment(org_id=a.org_id, user_id=user.id, branch_id=bid))
    db.execute(update(m.RefreshSession).where(m.RefreshSession.user_id == user.id).values(revoked_at=m.now()))
    audit(db, a, "staff.update", user.id, {"role": user.role, "active": user.active})
    return public(user, USER_FIELDS)


@staff.get("/permissions/roles")
def role_permissions(a: Actor = Depends(require("staff.manage")), db: Session = Depends(get_db, scope="function")):
    from app.permissions import PERMISSIONS

    return {k: sorted(v) for k, v in PERMISSIONS.items()}
