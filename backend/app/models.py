"""Tenant-owned normalized tables. Schema is installed ONLY through Alembic."""

from datetime import datetime, timezone, date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Date,
    Numeric,
    Boolean,
    Integer,
    JSON,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Tenant(Record):
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)


def scope(*constraints):
    return (UniqueConstraint("id", "org_id"), *constraints)


def ref(column, table):
    return ForeignKeyConstraint([column, "org_id"], [table + ".id", table + ".org_id"])


class Organization(Record, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    invoice_prefix: Mapped[str] = mapped_column(String(12), default="GYM")
    invoice_sequence: Mapped[int] = mapped_column(Integer, default=0)
    member_sequence: Mapped[int] = mapped_column(Integer, default=0)


class Branch(Tenant, Base):
    __tablename__ = "branches"
    __table_args__ = scope(UniqueConstraint("org_id", "name"))
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(500), default="")
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    opens: Mapped[str] = mapped_column(String(5), default="05:00")
    closes: Mapped[str] = mapped_column(String(5), default="23:00")
    grace_days: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Role(Record, Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(40), unique=True)


class Permission(Record, Base):
    __tablename__ = "permissions"
    name: Mapped[str] = mapped_column(String(60), unique=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("permissions.id"), primary_key=True)


class User(Tenant, Base):
    __tablename__ = "users"
    __table_args__ = scope(UniqueConstraint("org_id", "email"))
    email: Mapped[str] = mapped_column(String(254))
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(ForeignKey("roles.name"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class StaffAssignment(Tenant, Base):
    __tablename__ = "staff_assignments"
    __table_args__ = scope(
        ref("user_id", "users"), ref("branch_id", "branches"), UniqueConstraint("user_id", "branch_id")
    )
    user_id: Mapped[str] = mapped_column(String(36))
    branch_id: Mapped[str] = mapped_column(String(36))


class RefreshSession(Tenant, Base):
    __tablename__ = "refresh_sessions"
    __table_args__ = scope(ref("user_id", "users"))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    family_id: Mapped[str] = mapped_column(String(36), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    device: Mapped[str] = mapped_column(String(200), default="Browser")


class ActionToken(Tenant, Base):
    __tablename__ = "action_tokens"
    __table_args__ = scope(ref("user_id", "users"))
    user_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Member(Tenant, Base):
    __tablename__ = "members"
    __table_args__ = scope(
        ref("branch_id", "branches"),
        ref("user_id", "users"),
        UniqueConstraint("org_id", "member_code"),
        UniqueConstraint("org_id", "phone"),
        UniqueConstraint("user_id"),
    )
    branch_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36))
    member_code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120), index=True)
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str] = mapped_column(String(24))
    emergency_contact: Mapped[str] = mapped_column(String(250), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    photo_key: Mapped[str | None] = mapped_column(String(80))


class Plan(Tenant, Base):
    __tablename__ = "membership_plans"
    __table_args__ = scope(
        UniqueConstraint("org_id", "name"),
        CheckConstraint(
            "price >= 0 AND discount >= 0 AND discount <= price AND tax_rate >= 0 AND tax_rate <= 100 AND duration_days > 0"
        ),
    )
    name: Mapped[str] = mapped_column(String(120))
    duration_days: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    all_branches: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Membership(Tenant, Base):
    __tablename__ = "memberships"
    __table_args__ = scope(
        ref("member_id", "members"),
        ref("plan_id", "membership_plans"),
        ref("branch_id", "branches"),
        UniqueConstraint("org_id", "request_key"),
        CheckConstraint("end_date > start_date"),
    )
    member_id: Mapped[str] = mapped_column(String(36), index=True)
    plan_id: Mapped[str] = mapped_column(String(36))
    branch_id: Mapped[str] = mapped_column(String(36))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    all_branches: Mapped[bool] = mapped_column(Boolean, default=False)
    frozen_from: Mapped[date | None] = mapped_column(Date)
    frozen_until: Mapped[date | None] = mapped_column(Date)
    request_key: Mapped[str] = mapped_column(String(80))


class MembershipEvent(Tenant, Base):
    __tablename__ = "membership_events"
    __table_args__ = scope(ref("membership_id", "memberships"))
    membership_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(30))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Invoice(Tenant, Base):
    __tablename__ = "invoices"
    __table_args__ = scope(
        ref("member_id", "members"),
        ref("branch_id", "branches"),
        ref("membership_id", "memberships"),
        UniqueConstraint("org_id", "number"),
        UniqueConstraint("membership_id"),
        CheckConstraint("total >= 0"),
    )
    member_id: Mapped[str] = mapped_column(String(36), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), index=True)
    membership_id: Mapped[str | None] = mapped_column(String(36))
    number: Mapped[str] = mapped_column(String(40))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))


class InvoiceItem(Tenant, Base):
    __tablename__ = "invoice_items"
    __table_args__ = scope(ref("invoice_id", "invoices"))
    invoice_id: Mapped[str] = mapped_column(String(36), index=True)
    description: Mapped[str] = mapped_column(String(250))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class Payment(Tenant, Base):
    __tablename__ = "payments"
    __table_args__ = scope(
        ref("invoice_id", "invoices"), UniqueConstraint("org_id", "idempotency_key"), CheckConstraint("amount > 0")
    )
    invoice_id: Mapped[str] = mapped_column(String(36), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    method: Mapped[str] = mapped_column(String(30))
    reference: Mapped[str] = mapped_column(String(100), default="")
    idempotency_key: Mapped[str] = mapped_column(String(80))


class Refund(Tenant, Base):
    __tablename__ = "refunds"
    __table_args__ = scope(
        ref("payment_id", "payments"), UniqueConstraint("org_id", "idempotency_key"), CheckConstraint("amount > 0")
    )
    payment_id: Mapped[str] = mapped_column(String(36), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reason: Mapped[str] = mapped_column(String(500))
    idempotency_key: Mapped[str] = mapped_column(String(80))


class Expense(Tenant, Base):
    __tablename__ = "expenses"
    __table_args__ = scope(ref("branch_id", "branches"), CheckConstraint("amount > 0"))
    branch_id: Mapped[str] = mapped_column(String(36))
    category: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(250))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    expense_date: Mapped[date] = mapped_column(Date)


class Attendance(Tenant, Base):
    __tablename__ = "attendance"
    __table_args__ = scope(
        ref("member_id", "members"),
        ref("branch_id", "branches"),
        Index("uq_open_attendance", "member_id", unique=True, postgresql_where=text("checked_out_at IS NULL")),
        CheckConstraint("checked_out_at IS NULL OR checked_out_at >= checked_in_at"),
    )
    member_id: Mapped[str] = mapped_column(String(36), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), index=True)
    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(20), default="manual")


class QRToken(Tenant, Base):
    __tablename__ = "qr_tokens"
    __table_args__ = scope(ref("member_id", "members"))
    member_id: Mapped[str] = mapped_column(String(36))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Trainer(Tenant, Base):
    __tablename__ = "trainers"
    __table_args__ = scope(ref("user_id", "users"), ref("branch_id", "branches"), UniqueConstraint("user_id"))
    user_id: Mapped[str | None] = mapped_column(String(36))
    branch_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(120))
    specialties: Mapped[str] = mapped_column(String(250), default="")
    starts: Mapped[str] = mapped_column(String(5), default="06:00")
    ends: Mapped[str] = mapped_column(String(5), default="21:00")
    working_days: Mapped[list] = mapped_column(JSON, default=lambda: list(range(6)))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class TrainerAssignment(Tenant, Base):
    __tablename__ = "trainer_assignments"
    __table_args__ = scope(
        ref("trainer_id", "trainers"), ref("member_id", "members"), UniqueConstraint("trainer_id", "member_id")
    )
    trainer_id: Mapped[str] = mapped_column(String(36))
    member_id: Mapped[str] = mapped_column(String(36))


class TrainingPackage(Tenant, Base):
    __tablename__ = "training_packages"
    __table_args__ = scope(ref("member_id", "members"), ref("trainer_id", "trainers"), CheckConstraint("sessions > 0"))
    member_id: Mapped[str] = mapped_column(String(36))
    trainer_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(120))
    sessions: Mapped[int] = mapped_column(Integer)


class TrainingSession(Tenant, Base):
    __tablename__ = "training_sessions"
    __table_args__ = scope(
        ref("trainer_id", "trainers"),
        ref("member_id", "members"),
        ref("package_id", "training_packages"),
        CheckConstraint("ends_at > starts_at"),
    )
    trainer_id: Mapped[str] = mapped_column(String(36), index=True)
    member_id: Mapped[str] = mapped_column(String(36), index=True)
    package_id: Mapped[str] = mapped_column(String(36))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(20), default="booked")


class Exercise(Tenant, Base):
    __tablename__ = "exercises"
    __table_args__ = scope(UniqueConstraint("org_id", "name"))
    name: Mapped[str] = mapped_column(String(120))
    muscle_group: Mapped[str] = mapped_column(String(80))
    instructions: Mapped[str] = mapped_column(Text, default="")


class WorkoutPlan(Tenant, Base):
    __tablename__ = "workout_plans"
    __table_args__ = scope(ref("member_id", "members"), ref("trainer_id", "trainers"))
    name: Mapped[str] = mapped_column(String(120))
    member_id: Mapped[str | None] = mapped_column(String(36))
    trainer_id: Mapped[str | None] = mapped_column(String(36))
    description: Mapped[str] = mapped_column(Text, default="")
    scheduled_date: Mapped[date | None] = mapped_column(Date)


class WorkoutExercise(Tenant, Base):
    __tablename__ = "workout_exercises"
    __table_args__ = scope(ref("workout_plan_id", "workout_plans"), ref("exercise_id", "exercises"))
    workout_plan_id: Mapped[str] = mapped_column(String(36))
    exercise_id: Mapped[str] = mapped_column(String(36))
    sets: Mapped[int] = mapped_column(Integer)
    repetitions: Mapped[int] = mapped_column(Integer)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)


class WorkoutLog(Tenant, Base):
    __tablename__ = "workout_logs"
    __table_args__ = scope(ref("member_id", "members"), ref("exercise_id", "exercises"))
    member_id: Mapped[str] = mapped_column(String(36))
    exercise_id: Mapped[str] = mapped_column(String(36))
    performed_on: Mapped[date] = mapped_column(Date)
    sets: Mapped[int] = mapped_column(Integer)
    repetitions: Mapped[int] = mapped_column(Integer)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)


class Progress(Tenant, Base):
    __tablename__ = "progress"
    __table_args__ = scope(ref("member_id", "members"))
    member_id: Mapped[str] = mapped_column(String(36), index=True)
    measured_on: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    waist_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    notes: Mapped[str] = mapped_column(Text, default="")


class Supplier(Tenant, Base):
    __tablename__ = "suppliers"
    __table_args__ = scope()
    name: Mapped[str] = mapped_column(String(120))
    contact: Mapped[str] = mapped_column(String(250), default="")


class InventoryItem(Tenant, Base):
    __tablename__ = "inventory_items"
    __table_args__ = scope(
        ref("branch_id", "branches"),
        ref("supplier_id", "suppliers"),
        UniqueConstraint("org_id", "branch_id", "sku"),
        CheckConstraint("stock >= 0"),
    )
    branch_id: Mapped[str] = mapped_column(String(36))
    supplier_id: Mapped[str | None] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(120))
    sku: Mapped[str] = mapped_column(String(60))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_level: Mapped[int] = mapped_column(Integer, default=5)


class StockMovement(Tenant, Base):
    __tablename__ = "stock_movements"
    __table_args__ = scope(ref("item_id", "inventory_items"))
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(250))


class Equipment(Tenant, Base):
    __tablename__ = "equipment"
    __table_args__ = scope(ref("branch_id", "branches"), UniqueConstraint("org_id", "serial"))
    branch_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(120))
    serial: Mapped[str] = mapped_column(String(80))
    assigned_to: Mapped[str] = mapped_column(String(120), default="")
    next_service: Mapped[date] = mapped_column(Date)
    state: Mapped[str] = mapped_column(String(20), default="operational")


class Maintenance(Tenant, Base):
    __tablename__ = "maintenance"
    __table_args__ = scope(ref("equipment_id", "equipment"), ref("expense_id", "expenses"))
    equipment_id: Mapped[str] = mapped_column(String(36))
    expense_id: Mapped[str | None] = mapped_column(String(36))
    serviced_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(String(1000))
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class Notification(Tenant, Base):
    __tablename__ = "notifications"
    __table_args__ = scope(ref("user_id", "users"), UniqueConstraint("org_id", "dedupe_key"))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(1000))
    dedupe_key: Mapped[str] = mapped_column(String(200))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Tenant, Base):
    __tablename__ = "audit_logs"
    __table_args__ = scope(ref("actor_id", "users"))
    actor_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
