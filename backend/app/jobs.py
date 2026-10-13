"""Run as a separate process: python -m app.jobs. Restartable, deduplicated in-app delivery."""

import logging, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from app.db import SessionLocal
from app import models as m
from app.permissions import OWNER_ROLES

log = logging.getLogger("gymos.jobs")


def notify(db, org, user, title, body, key):
    db.execute(
        insert(m.Notification)
        .values(id=m.uid(), created_at=m.now(), org_id=org, user_id=user, title=title, body=body, dedupe_key=key)
        .on_conflict_do_nothing(index_elements=["org_id", "dedupe_key"])
    )


def run_once():
    delivered = 0
    with SessionLocal.begin() as db:
        for org in db.scalars(select(m.Organization)):
            today = datetime.now(ZoneInfo(org.timezone)).date()
            memberships = db.scalars(
                select(m.Membership).where(
                    m.Membership.org_id == org.id,
                    m.Membership.state == "active",
                    m.Membership.end_date >= today,
                    m.Membership.end_date <= today + timedelta(days=7),
                )
            ).all()
            owners = db.scalars(
                select(m.User.id).where(m.User.org_id == org.id, m.User.active.is_(True), m.User.role.in_(OWNER_ROLES))
            ).all()
            for ms in memberships:
                member = db.scalar(select(m.Member).where(m.Member.id == ms.member_id, m.Member.org_id == org.id))
                targets = ([member.user_id] if member.user_id else []) + owners
                for user in set(targets):
                    notify(
                        db,
                        org.id,
                        user,
                        "Membership renewal approaching",
                        f"{member.member_code}: access ends on {ms.end_date.isoformat()} (exclusive).",
                        f"expiry:{ms.id}:{ms.end_date}:{user}:{today}",
                    )
                    delivered += 1
            for session in db.scalars(
                select(m.TrainingSession).where(
                    m.TrainingSession.org_id == org.id,
                    m.TrainingSession.state == "booked",
                    m.TrainingSession.starts_at >= m.now(),
                    m.TrainingSession.starts_at < m.now() + timedelta(hours=24),
                )
            ):
                member = db.get(m.Member, session.member_id)
                trainer = db.get(m.Trainer, session.trainer_id)
                for user in set(x for x in [member.user_id, trainer.user_id] if x):
                    notify(
                        db,
                        org.id,
                        user,
                        "Upcoming training session",
                        "Your session starts at " + session.starts_at.isoformat() + ".",
                        f"session:{session.id}:{session.starts_at.isoformat()}:{user}",
                    )
            for item in db.scalars(
                select(m.InventoryItem).where(
                    m.InventoryItem.org_id == org.id, m.InventoryItem.stock <= m.InventoryItem.low_stock_level
                )
            ):
                for user in owners:
                    notify(
                        db,
                        org.id,
                        user,
                        "Low stock",
                        f"{item.name}: {item.stock} remaining.",
                        f"stock:{item.id}:{today}:{user}",
                    )
            for item in db.scalars(
                select(m.Equipment).where(
                    m.Equipment.org_id == org.id, m.Equipment.next_service <= today, m.Equipment.state != "retired"
                )
            ):
                for user in owners:
                    notify(
                        db,
                        org.id,
                        user,
                        "Equipment maintenance due",
                        item.name + " needs service.",
                        f"service:{item.id}:{today}:{user}",
                    )
        db.execute(delete(m.QRToken).where(m.QRToken.expires_at < m.now() - timedelta(days=1)))
        db.execute(delete(m.ActionToken).where(m.ActionToken.expires_at < m.now() - timedelta(days=7)))
        db.execute(delete(m.RefreshSession).where(m.RefreshSession.expires_at < m.now() - timedelta(days=30)))
        db.execute(delete(m.RateBucket).where(m.RateBucket.expires_at < m.now()))
    return delivered


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    failures = 0
    while True:
        try:
            run_once()
            failures = 0
            time.sleep(60)
        except Exception as exc:
            failures += 1
            log.error("Notification pass failed (%s); will retry", type(exc).__name__)
            time.sleep(min(60, 2 ** min(failures, 6)))
