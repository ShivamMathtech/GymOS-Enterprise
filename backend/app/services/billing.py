from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import select, func
from app import models as m
from app.deps import owned
from app.services.common import audit, public

CENT = Decimal("0.01")


def money(v):
    return Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP)


def line_total(quantity, price, discount, tax_rate):
    subtotal = money(quantity * price - discount)
    tax = money(subtotal * tax_rate / Decimal("100"))
    return tax, money(subtotal + tax)


def amounts(db, invoice):
    paid = db.scalar(
        select(func.coalesce(func.sum(m.Payment.amount), 0)).where(
            m.Payment.org_id == invoice.org_id, m.Payment.invoice_id == invoice.id
        )
    )
    refunded = db.scalar(
        select(func.coalesce(func.sum(m.Refund.amount), 0))
        .join(m.Payment, m.Payment.id == m.Refund.payment_id)
        .where(m.Refund.org_id == invoice.org_id, m.Payment.invoice_id == invoice.id)
    )
    net = money(paid - refunded)
    return {
        "paid": money(paid),
        "refunded": money(refunded),
        "net_paid": net,
        "balance": money(0 if invoice.cancelled_at else max(Decimal(0), invoice.total - net)),
    }


def invoice_dto(db, invoice):
    values = amounts(db, invoice)
    status = (
        "cancelled"
        if invoice.cancelled_at
        else ("paid" if values["balance"] == 0 else ("partial" if values["net_paid"] > 0 else "unpaid"))
    )
    return dict(
        public(
            invoice,
            "id created_at member_id branch_id membership_id number total currency cancelled_at cancellation_reason",
        ),
        **{k: str(v) for k, v in values.items()},
        status=status,
    )


def new_invoice(db, a, member, lines, membership=None):
    # Lock invoice counter until the transaction commits, yielding gap-free committed numbers.
    org = db.scalar(select(m.Organization).where(m.Organization.id == a.org_id).with_for_update())
    org.invoice_sequence += 1
    invoice = m.Invoice(
        org_id=a.org_id,
        member_id=member.id,
        branch_id=member.branch_id,
        membership_id=membership.id if membership else None,
        number=f"{org.invoice_prefix}-{org.invoice_sequence:07d}",
        total=Decimal("0"),
        currency=org.currency,
    )
    db.add(invoice)
    db.flush()
    total = Decimal("0")
    for line in lines:
        tax, line_sum = line_total(line.quantity, line.unit_price, line.discount, line.tax_rate)
        total += line_sum
        db.add(
            m.InvoiceItem(
                org_id=a.org_id,
                invoice_id=invoice.id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount=line.discount,
                tax_rate=line.tax_rate,
                tax_amount=tax,
                total=line_sum,
            )
        )
    if total > Decimal("9999999999.99"):
        raise HTTPException(422, "Invoice total exceeds supported range")
    invoice.total = money(total)
    if membership and total == 0:
        membership.state = "active"
    audit(db, a, "invoice.create", invoice.id)
    return invoice


def refresh_membership(db, a, invoice):
    if not invoice.membership_id:
        return
    membership = owned(db, m.Membership, invoice.membership_id, a, lock=True)
    if membership.state == "cancelled":
        return
    desired = "active" if amounts(db, invoice)["balance"] == 0 and not invoice.cancelled_at else "pending"
    if desired != membership.state:
        membership.state = desired
        db.add(
            m.MembershipEvent(
                org_id=a.org_id, membership_id=membership.id, action="payment_status", details={"state": desired}
            )
        )


def take_payment(db, a, data):
    invoice = owned(db, m.Invoice, data.invoice_id, a, lock=True)
    old = db.scalar(
        select(m.Payment).where(m.Payment.org_id == a.org_id, m.Payment.idempotency_key == data.idempotency_key)
    )
    if old:
        if (old.invoice_id, old.amount, old.method, old.reference) != (
            data.invoice_id,
            data.amount,
            data.method,
            data.reference,
        ):
            raise HTTPException(409, "Idempotency key already used with different data")
        return old
    if invoice.cancelled_at:
        raise HTTPException(409, "Invoice cancelled")
    if data.amount > amounts(db, invoice)["balance"]:
        raise HTTPException(409, "Payment exceeds outstanding balance")
    payment = m.Payment(org_id=a.org_id, **data.model_dump())
    db.add(payment)
    db.flush()
    refresh_membership(db, a, invoice)
    audit(
        db,
        a,
        "payment.record",
        payment.id,
        {"invoice_id": invoice.id, "amount": str(payment.amount), "method": payment.method},
    )
    member = owned(db, m.Member, invoice.member_id, a)
    if member.user_id:
        db.add(
            m.Notification(
                org_id=a.org_id,
                user_id=member.user_id,
                title="Payment recorded",
                body=f"Payment of {payment.amount} {invoice.currency} recorded for invoice {invoice.number}.",
                dedupe_key="payment:" + payment.id,
            )
        )
    return payment


def issue_refund(db, a, data):
    original = owned(db, m.Payment, data.payment_id, a)
    invoice = owned(db, m.Invoice, original.invoice_id, a, lock=True)
    old = db.scalar(
        select(m.Refund).where(m.Refund.org_id == a.org_id, m.Refund.idempotency_key == data.idempotency_key)
    )
    if old:
        if (old.payment_id, old.amount, old.reason) != (data.payment_id, data.amount, data.reason):
            raise HTTPException(409, "Idempotency key already used with different data")
        return old
    refunded = db.scalar(
        select(func.coalesce(func.sum(m.Refund.amount), 0)).where(
            m.Refund.org_id == a.org_id, m.Refund.payment_id == original.id
        )
    )
    if data.amount > original.amount - refunded:
        raise HTTPException(409, "Refund exceeds unrefunded payment")
    row = m.Refund(org_id=a.org_id, **data.model_dump())
    db.add(row)
    db.flush()
    refresh_membership(db, a, invoice)
    audit(
        db, a, "payment.refund", row.id, {"payment_id": original.id, "amount": str(data.amount), "reason": data.reason}
    )
    return row
