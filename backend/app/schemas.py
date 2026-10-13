from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator, model_validator

ID = Annotated[str, Field(min_length=36, max_length=36)]
Name = Annotated[str, Field(min_length=1, max_length=120)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Key = Annotated[str, Field(min_length=8, max_length=80)]
Password = Annotated[str, Field(min_length=12, max_length=128)]


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TimezoneDTO(DTO):
    timezone: str = "Asia/Kolkata"

    @field_validator("timezone")
    @classmethod
    def tz(cls, v):
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError:
            raise ValueError("Unknown IANA time zone")
        return v


class Register(TimezoneDTO):
    organization: Name
    slug: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{2,59}$")]
    name: Name
    email: EmailStr
    password: Password


class Login(DTO):
    organization: str = Field(min_length=3, max_length=60)
    email: EmailStr
    password: str = Field(max_length=128)


class Forgot(DTO):
    organization: str = Field(max_length=60)
    email: EmailStr


class Reset(DTO):
    token: str = Field(min_length=20, max_length=200)
    password: Password


class Invite(DTO):
    name: Name
    email: EmailStr
    role: Literal["Gym Owner", "Manager", "Receptionist", "Trainer", "Accountant", "Member"]
    branch_ids: list[ID] = Field(default_factory=list, max_length=100)
    member_id: ID | None = None


class StaffUpdate(DTO):
    role: Literal["Gym Owner", "Manager", "Receptionist", "Trainer", "Accountant", "Member"]
    active: bool
    branch_ids: list[ID] = Field(default_factory=list, max_length=100)


class OrganizationUpdate(TimezoneDTO):
    name: Name
    invoice_prefix: str = Field(pattern=r"^[A-Z0-9-]{1,12}$")


class BranchIn(TimezoneDTO):
    name: Name
    address: str = Field(default="", max_length=500)
    opens: str = Field(default="05:00", pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    closes: str = Field(default="23:00", pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    grace_days: int = Field(default=0, ge=0, le=30)
    active: bool = True


class MemberIn(DTO):
    branch_id: ID
    name: Name
    email: EmailStr | None = None
    phone: str = Field(pattern=r"^\+?[0-9][0-9 -]{6,22}$")
    emergency_contact: str = Field(default="", max_length=250)
    notes: str = Field(default="", max_length=4000)

    @field_validator("phone")
    @classmethod
    def phone_clean(cls, v):
        return v.replace(" ", "").replace("-", "")


class MemberEdit(DTO):
    name: Name | None = None
    email: EmailStr | None = None
    phone: str | None = None
    emergency_contact: str | None = Field(default=None, max_length=250)
    notes: str | None = Field(default=None, max_length=4000)
    status: Literal["active", "inactive", "archived"] | None = None


class PlanIn(DTO):
    name: Name
    duration_days: int = Field(ge=1, le=3660)
    price: Money
    discount: Money = Decimal("0")
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2)
    all_branches: bool = False
    active: bool = True

    @model_validator(mode="after")
    def discount_valid(self):
        if self.discount > self.price:
            raise ValueError("Discount cannot exceed price")
        return self


class MembershipIn(DTO):
    member_id: ID
    plan_id: ID
    start_date: date
    request_key: Key


class RenewalIn(DTO):
    plan_id: ID
    request_key: Key


class LifecycleIn(DTO):
    action: Literal["freeze", "extend", "cancel"]
    days: int = Field(default=0, ge=0, le=366)
    reason: str = Field(min_length=3, max_length=500)


class InvoiceLineIn(DTO):
    description: str = Field(min_length=1, max_length=250)
    quantity: int = Field(ge=1, le=10000)
    unit_price: Money
    discount: Money = Decimal("0")
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2)

    @model_validator(mode="after")
    def valid(self):
        if self.discount > self.unit_price * self.quantity:
            raise ValueError("Discount exceeds line subtotal")
        return self


class InvoiceIn(DTO):
    member_id: ID
    lines: list[InvoiceLineIn] = Field(min_length=1, max_length=100)


class PaymentIn(DTO):
    invoice_id: ID
    amount: PositiveMoney
    method: Literal["cash", "upi", "card", "bank_transfer", "other"]
    reference: str = Field(default="", max_length=100)
    idempotency_key: Key


class RefundIn(DTO):
    payment_id: ID
    amount: PositiveMoney
    reason: str = Field(min_length=3, max_length=500)
    idempotency_key: Key


class Reason(DTO):
    reason: str = Field(min_length=3, max_length=500)


class ExpenseIn(DTO):
    branch_id: ID
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=250)
    amount: PositiveMoney
    expense_date: date


class CheckIn(DTO):
    member_id: ID
    branch_id: ID


class QRCheckIn(DTO):
    token: str = Field(min_length=20, max_length=200)
    branch_id: ID


class Correction(DTO):
    checked_in_at: datetime
    checked_out_at: datetime | None = None
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def dates(self):
        for v in (self.checked_in_at, self.checked_out_at):
            if v and v.tzinfo is None:
                raise ValueError("Timestamps require a timezone")
        if self.checked_out_at and self.checked_out_at < self.checked_in_at:
            raise ValueError("Checkout precedes check-in")
        return self


class TrainerIn(DTO):
    branch_id: ID
    user_id: ID | None = None
    name: Name
    specialties: str = Field(default="", max_length=250)
    starts: str = Field(default="06:00", pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    ends: str = Field(default="21:00", pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    working_days: list[Annotated[int, Field(ge=0, le=6)]] = Field(
        default_factory=lambda: list(range(6)), min_length=1, max_length=7
    )
    active: bool = True


class AssignmentIn(DTO):
    trainer_id: ID
    member_id: ID


class PackageIn(AssignmentIn):
    name: Name
    sessions: int = Field(ge=1, le=1000)


class SessionIn(AssignmentIn):
    package_id: ID
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def dates(self):
        if not self.starts_at.tzinfo or not self.ends_at.tzinfo:
            raise ValueError("Timestamps require a timezone")
        seconds = (self.ends_at - self.starts_at).total_seconds()
        if seconds < 300 or seconds > 14400:
            raise ValueError("Sessions must last 5–240 minutes")
        return self


class SessionState(DTO):
    state: Literal["cancelled", "completed", "no_show"]


class ExerciseIn(DTO):
    name: Name
    muscle_group: str = Field(min_length=1, max_length=80)
    instructions: str = Field(default="", max_length=4000)


class WorkoutIn(DTO):
    name: Name
    member_id: ID | None = None
    trainer_id: ID | None = None
    description: str = Field(default="", max_length=4000)
    scheduled_date: date | None = None


class WorkoutExerciseIn(DTO):
    workout_plan_id: ID
    exercise_id: ID
    sets: int = Field(ge=1, le=100)
    repetitions: int = Field(ge=1, le=1000)
    weight_kg: Decimal = Field(default=0, ge=0, le=1000, decimal_places=2)
    duration_seconds: int = Field(default=0, ge=0, le=86400)


class WorkoutLogIn(DTO):
    member_id: ID
    exercise_id: ID
    performed_on: date
    sets: int = Field(ge=1, le=100)
    repetitions: int = Field(ge=1, le=1000)
    weight_kg: Decimal = Field(default=0, ge=0, le=1000, decimal_places=2)
    duration_seconds: int = Field(default=0, ge=0, le=86400)


class ProgressIn(DTO):
    member_id: ID
    measured_on: date
    weight_kg: Decimal = Field(gt=0, le=700, decimal_places=2)
    waist_cm: Decimal | None = Field(default=None, gt=0, le=400, decimal_places=2)
    notes: str = Field(default="", max_length=4000)


class SupplierIn(DTO):
    name: Name
    contact: str = Field(default="", max_length=250)


class InventoryIn(DTO):
    branch_id: ID
    supplier_id: ID | None = None
    name: Name
    sku: str = Field(min_length=1, max_length=60)
    low_stock_level: int = Field(default=5, ge=0, le=100000)


class StockIn(DTO):
    item_id: ID
    quantity: int = Field(ge=-100000, le=100000)
    reason: str = Field(min_length=3, max_length=250)


class EquipmentIn(DTO):
    branch_id: ID
    name: Name
    serial: str = Field(min_length=1, max_length=80)
    assigned_to: str = Field(default="", max_length=120)
    next_service: date
    state: Literal["operational", "maintenance", "retired"] = "operational"


class MaintenanceIn(DTO):
    equipment_id: ID
    serviced_on: date
    notes: str = Field(min_length=3, max_length=1000)
    cost: Money
    next_service: date
