"""Opt-in local demo. No data is inserted on application startup."""

import secrets, os
from pathlib import Path
from decimal import Decimal
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app import models as m
from app.security import hash_password


def main():
    if settings().app_env != "development":
        raise SystemExit("Demo seeding is development-only")
    with SessionLocal.begin() as db:
        if db.scalar(select(m.Organization).where(m.Organization.slug == "demo-gym")):
            print("Demo organization already exists; no changes made.")
            return
        password = secrets.token_urlsafe(18)
        org = m.Organization(name="Demo Fitness Club", slug="demo-gym")
        db.add(org)
        db.flush()
        user = m.User(
            org_id=org.id,
            name="Demo Owner",
            email="owner@example.com",
            role="Gym Owner",
            password_hash=hash_password(password),
        )
        db.add(user)
        branch = m.Branch(org_id=org.id, name="Main Club", opens="00:00", closes="00:00")
        db.add(branch)
        db.flush()
        db.add(
            m.Plan(
                org_id=org.id,
                name="Monthly Access",
                duration_days=30,
                price=Decimal("1500.00"),
                discount=Decimal("0"),
                tax_rate=Decimal("0"),
            )
        )
        path = Path("../.local-credentials.txt")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(
                "DEVELOPMENT DEMO ONLY\nOrganization: demo-gym\nEmail: owner@example.com\nPassword: " + password + "\n"
            )
    print("Demo owner, branch and plan created. Open .local-credentials.txt in the project root for sign-in details.")


if __name__ == "__main__":
    main()
