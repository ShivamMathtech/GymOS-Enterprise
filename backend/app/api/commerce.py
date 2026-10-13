from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from html import escape
from app import models as m, schemas as s
from app.db import get_db
from app.deps import Actor, require, owned, get_member, member_scope
from app.services.common import public, page, audit
from app.services import billing, memberships

router = APIRouter(tags=["Memberships & finance"])


@router.get("/plans")
def plans(a: Actor = Depends(require("plans.read")), db: Session = Depends(get_db, scope="function")):
    return [
        public(r, "id name duration_days price discount tax_rate all_branches active")
        for r in db.scalars(select(m.Plan).where(m.Plan.org_id == a.org_id).order_by(m.Plan.name))
    ]


@router.post("/plans", status_code=201)
def create_plan(
    data: s.PlanIn, a: Actor = Depends(require("plans.write")), db: Session = Depends(get_db, scope="function")
):
    row = m.Plan(org_id=a.org_id, **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, a, "plan.create", row.id)
    return public(row, "id name duration_days price discount tax_rate all_branches active")


@router.put("/plans/{key}")
def edit_plan(
    key: str,
    data: s.PlanIn,
    a: Actor = Depends(require("plans.write")),
    db: Session = Depends(get_db, scope="function"),
):
    row = owned(db, m.Plan, key, a, lock=True)
    for k, v in data.model_dump().items():
        setattr(row, k, v)
    audit(db, a, "plan.update", row.id)
    return public(row, "id name duration_days price discount tax_rate all_branches active")


@router.get("/memberships")
def list_memberships(
    member_id: str | None = None,
    page_no: int = Query(1, ge=1, alias="page"),
    size: int = Query(25, ge=1, le=100),
    a: Actor = Depends(require("memberships.read")),
    db: Session = Depends(get_db, scope="function"),
):
    ids = member_scope(db, a, select(m.Member.id))
    q = select(m.Membership).where(m.Membership.org_id == a.org_id, m.Membership.member_id.in_(ids))
    if member_id:
        get_member(db, member_id, a)
        q = q.where(m.Membership.member_id == member_id)
    rows, total = page(db, q, m.Membership, page_no, size)
    return {"items": [memberships.dto(db, a, r) for r in rows], "total": total, "page": page_no, "size": size}


@router.post("/memberships", status_code=201)
def assign(
    data: s.MembershipIn,
    a: Actor = Depends(require("memberships.write")),
    db: Session = Depends(get_db, scope="function"),
):
    return memberships.dto(db, a, memberships.assign(db, a, data))


@router.post("/memberships/{key}/renew", status_code=201)
def renew(
    key: str,
    data: s.RenewalIn,
    a: Actor = Depends(require("memberships.write")),
    db: Session = Depends(get_db, scope="function"),
):
    return memberships.dto(db, a, memberships.renew(db, a, key, data))


@router.post("/memberships/{key}/lifecycle")
def lifecycle(
    key: str,
    data: s.LifecycleIn,
    a: Actor = Depends(require("memberships.write")),
    db: Session = Depends(get_db, scope="function"),
):
    return memberships.dto(db, a, memberships.lifecycle(db, a, key, data))


@router.get("/memberships/{key}/events")
def events(key: str, a: Actor = Depends(require("memberships.read")), db: Session = Depends(get_db, scope="function")):
    row = owned(db, m.Membership, key, a)
    get_member(db, row.member_id, a)
    return [
        public(r, "id created_at action details")
        for r in db.scalars(
            select(m.MembershipEvent)
            .where(m.MembershipEvent.org_id == a.org_id, m.MembershipEvent.membership_id == key)
            .order_by(m.MembershipEvent.created_at)
        )
    ]


@router.get("/invoices")
def invoices(
    member_id: str | None = None,
    branch_id: str | None = None,
    page_no: int = Query(1, ge=1, alias="page"),
    size: int = Query(25, ge=1, le=100),
    a: Actor = Depends(require("finance.read")),
    db: Session = Depends(get_db, scope="function"),
):
    q = select(m.Invoice).where(m.Invoice.org_id == a.org_id)
    if a.branches is not None:
        q = q.where(m.Invoice.branch_id.in_(a.branches))
    if branch_id:
        a.branch(branch_id)
        q = q.where(m.Invoice.branch_id == branch_id)
    if member_id:
        get_member(db, member_id, a)
        q = q.where(m.Invoice.member_id == member_id)
    rows, total = page(db, q, m.Invoice, page_no, size)
    return {"items": [billing.invoice_dto(db, r) for r in rows], "total": total, "page": page_no, "size": size}


@router.post("/invoices", status_code=201)
def create_invoice(
    data: s.InvoiceIn, a: Actor = Depends(require("finance.write")), db: Session = Depends(get_db, scope="function")
):
    member = get_member(db, data.member_id, a)
    return billing.invoice_dto(db, billing.new_invoice(db, a, member, data.lines))


@router.get("/invoices/{key}")
def invoice_details(
    key: str, a: Actor = Depends(require("finance.read")), db: Session = Depends(get_db, scope="function")
):
    row = owned(db, m.Invoice, key, a)
    result = billing.invoice_dto(db, row)
    result["items"] = [
        public(r, "id description quantity unit_price discount tax_rate tax_amount total")
        for r in db.scalars(
            select(m.InvoiceItem).where(m.InvoiceItem.org_id == a.org_id, m.InvoiceItem.invoice_id == key)
        )
    ]
    payments = db.scalars(select(m.Payment).where(m.Payment.org_id == a.org_id, m.Payment.invoice_id == key)).all()
    result["payments"] = [public(p, "id created_at amount method reference") for p in payments]
    result["refunds"] = [
        public(r, "id created_at payment_id amount reason")
        for r in db.scalars(
            select(m.Refund).where(m.Refund.org_id == a.org_id, m.Refund.payment_id.in_([p.id for p in payments]))
        )
    ]
    return result


@router.post("/invoices/{key}/cancel")
def cancel_invoice(
    key: str,
    data: s.Reason,
    a: Actor = Depends(require("finance.write")),
    db: Session = Depends(get_db, scope="function"),
):
    row = owned(db, m.Invoice, key, a, lock=True)
    if billing.amounts(db, row)["net_paid"] != 0:
        raise HTTPException(409, "Refund net payments before cancelling the invoice")
    row.cancelled_at = m.now()
    row.cancellation_reason = data.reason
    if row.membership_id:
        owned(db, m.Membership, row.membership_id, a, lock=True).state = "cancelled"
    audit(db, a, "invoice.cancel", key, {"reason": data.reason})
    return billing.invoice_dto(db, row)


@router.post("/payments", status_code=201)
def payment(
    data: s.PaymentIn, a: Actor = Depends(require("finance.read")), db: Session = Depends(get_db, scope="function")
):
    if not {"finance.write", "finance.collect"} & a.permissions:
        raise HTTPException(403, "Permission denied")
    row = billing.take_payment(db, a, data)
    return public(row, "id created_at invoice_id amount method reference")


@router.post("/refunds", status_code=201)
def refund(
    data: s.RefundIn, a: Actor = Depends(require("finance.write")), db: Session = Depends(get_db, scope="function")
):
    return public(billing.issue_refund(db, a, data), "id created_at payment_id amount reason")


@router.get("/payments/{key}/receipt", response_class=HTMLResponse)
def receipt(key: str, a: Actor = Depends(require("finance.read")), db: Session = Depends(get_db, scope="function")):
    payment = owned(db, m.Payment, key, a)
    invoice = owned(db, m.Invoice, payment.invoice_id, a)
    org = db.get(m.Organization, a.org_id)
    # Printable HTML; frontend opens an authenticated blob, never an access token in a URL.
    return (
        '<!doctype html><html><meta charset="utf-8"><title>Payment receipt</title><style>body{font:16px system-ui;max-width:700px;margin:60px auto;padding:20px}h1{color:#155eef}dl{line-height:2}small{color:#555}</style><h1>'
        + escape(org.name)
        + "</h1><h2>Payment receipt</h2><dl><dt>Receipt ID</dt><dd>"
        + escape(payment.id)
        + "</dd><dt>Invoice</dt><dd>"
        + escape(invoice.number)
        + "</dd><dt>Recorded (UTC)</dt><dd>"
        + payment.created_at.isoformat()
        + "</dd><dt>Amount</dt><dd>"
        + str(payment.amount)
        + " "
        + escape(invoice.currency)
        + "</dd><dt>Method</dt><dd>"
        + escape(payment.method)
        + "</dd></dl><small>Manual payment record. Refunds, if any, are recorded separately in the invoice history. Use your browser’s Print command to save as PDF.</small></html>"
    )
