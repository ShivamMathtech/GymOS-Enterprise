"""Explicit first-organization bootstrap for a fresh deployment; prompts for the owner password."""

from getpass import getpass
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Organization, User
from app.schemas import Register
from app.security import hash_password


def main():
    data = Register(
        organization=input("Organization name: "),
        slug=input("Organization ID (lowercase): "),
        name=input("Owner name: "),
        email=input("Owner email: "),
        password=getpass("Owner password (12+ characters): "),
    )
    with SessionLocal.begin() as db:
        if db.scalar(select(Organization).where(Organization.slug == data.slug)):
            raise SystemExit("Organization ID already exists")
        org = Organization(name=data.organization, slug=data.slug, timezone=data.timezone)
        db.add(org)
        db.flush()
        db.add(
            User(
                org_id=org.id,
                name=data.name,
                email=str(data.email).lower(),
                role="Gym Owner",
                password_hash=hash_password(data.password),
            )
        )
    print("Owner account created. Sign in and add a branch.")


if __name__ == "__main__":
    main()
