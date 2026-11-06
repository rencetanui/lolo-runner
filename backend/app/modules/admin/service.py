import csv
import io
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.audit.service import entries_for
from app.modules.auth.models import User
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.payments.service import PaymentError
from app.modules.refunds.models import Refund, RefundStatus
from app.modules.refunds.service import RefundError
from app.modules.registrations.models import Registration
from app.utils.csvsafe import csv_safe
from app.utils.dates import KENYA_TZ

from .schemas import (
    AdminPaymentDetail, AdminPaymentOut, AdminPaymentPage, AdminRefundDetail, AdminRefundOut,
    AdminRefundPage, AdminSummary, AuditOut, EventRef, PersonOut, RefundBrief,
)

STUCK_AFTER = timedelta(minutes=10)
MAX_EXPORT_DAYS = 366


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _stuck(now: datetime):
    return and_(Payment.status == PaymentStatus.pending, Payment.created_at < now - STUCK_AFTER)


def summary(db: Session) -> AdminSummary:
    now = _now()

    def count(*conds) -> int:
        return db.scalar(select(func.count(Payment.id)).where(*conds)) or 0

    return AdminSummary(
        needs_review=count(Payment.status == PaymentStatus.needs_review),
        needs_refund=count(Payment.needs_refund.is_(True)),
        stuck_pending=count(_stuck(now)),
        failed_24h=count(Payment.status == PaymentStatus.failed, Payment.completed_at > now - timedelta(hours=24)),
        refunds_requested=db.scalar(
            select(func.count(Refund.id)).where(Refund.status == RefundStatus.requested)
        ) or 0,
    )


# ------------------------------------------------------------------ payments
def _out(payment: Payment, reg: Registration, user: User) -> AdminPaymentOut:
    return AdminPaymentOut(
        id=payment.id, created_at=payment.created_at, completed_at=payment.completed_at,
        status=payment.status, amount=payment.amount, phone=payment.phone,
        mpesa_receipt=payment.mpesa_receipt, result_code=payment.result_code,
        result_desc=payment.result_desc, needs_refund=payment.needs_refund, admin_note=payment.admin_note,
        user=PersonOut(id=user.id, full_name=user.full_name, email=user.email),
        event=EventRef(id=reg.event.id, name=reg.event.name, event_date=reg.event.event_date),
        distance_name=reg.distance.name, bib_number=reg.bib_number,
        registration_id=reg.id, registration_status=reg.status,
    )


def _joined(stmt):
    return stmt.join(Registration, Registration.id == Payment.registration_id).join(User, User.id == Payment.user_id)


def _audit(db: Session, entity_type: str, entity_id) -> list[AuditOut]:
    out = []
    for entry in entries_for(db, entity_type, entity_id):
        actor = db.get(User, entry.actor_id) if entry.actor_id else None
        out.append(AuditOut(
            created_at=entry.created_at, action=entry.action,
            actor_name=actor.full_name if actor else None, detail=entry.detail,
        ))
    return out


def list_payments(
    db: Session, *, status: PaymentStatus | None, attention: bool, q: str | None, page: int, page_size: int
) -> AdminPaymentPage:
    conds = []
    if status:
        conds.append(Payment.status == status)
    if attention:
        conds.append(or_(
            Payment.status == PaymentStatus.needs_review,
            Payment.needs_refund.is_(True),
            _stuck(_now()),
        ))
    if q and q.strip():
        like = f"%{q.strip()}%"
        search = [
            User.email.ilike(like), User.full_name.ilike(like),
            Payment.phone.ilike(like), Payment.mpesa_receipt.ilike(like),
        ]
        if q.strip().isdigit():
            search.append(Registration.bib_number == int(q.strip()))
        conds.append(or_(*search))

    total = db.scalar(_joined(select(func.count(Payment.id))).where(*conds)) or 0
    rows = db.execute(
        _joined(select(Payment, Registration, User))
        .where(*conds)
        .order_by(Payment.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    return AdminPaymentPage(items=[_out(p, r, u) for p, r, u in rows], total=total)


def get_payment(db: Session, payment_id: uuid.UUID) -> AdminPaymentDetail:
    row = db.execute(_joined(select(Payment, Registration, User)).where(Payment.id == payment_id)).first()
    if row is None:
        raise PaymentError("payment_not_found", "Payment not found", 404)
    payment, reg, user = row
    refunds = db.scalars(select(Refund).where(Refund.payment_id == payment.id).order_by(Refund.created_at))
    return AdminPaymentDetail(
        **_out(payment, reg, user).model_dump(),
        raw_callback=payment.raw_callback,
        audit=_audit(db, "payment", payment.id),
        refunds=[
            RefundBrief(
                id=r.id, status=r.status, reason=r.reason, amount=r.amount,
                created_at=r.created_at, mpesa_reference=r.mpesa_reference,
            )
            for r in refunds
        ],
    )


def payments_csv(db: Session, start: date, end: date) -> tuple[str, str]:
    """Every payment created between two Nairobi dates (inclusive), for matching against the M-Pesa statement."""
    if end < start or (end - start).days > MAX_EXPORT_DAYS:
        raise PaymentError("invalid_range", "Choose a start date on or before the end date, at most a year apart.", 422)
    lo = datetime.combine(start, time.min, tzinfo=KENYA_TZ).astimezone(timezone.utc)
    hi = datetime.combine(end + timedelta(days=1), time.min, tzinfo=KENYA_TZ).astimezone(timezone.utc)
    rows = db.execute(
        _joined(select(Payment, Registration, User))
        .where(Payment.created_at >= lo, Payment.created_at < hi)
        .order_by(Payment.created_at)
    ).all()

    def eat(dt: datetime | None) -> str:
        dt = _aware(dt)
        return dt.astimezone(KENYA_TZ).strftime("%Y-%m-%d %H:%M") if dt else ""

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Payment ID", "Created (EAT)", "Completed (EAT)", "Status", "Amount (KES)", "Phone", "M-Pesa receipt",
        "Needs refund", "Runner", "Email", "Event", "Distance", "Bib", "Registration status", "Admin note",
    ])
    for p, reg, user in rows:
        writer.writerow([
            p.id, eat(p.created_at), eat(p.completed_at), p.status.value, int(p.amount), p.phone,
            csv_safe(p.mpesa_receipt), "yes" if p.needs_refund else "", csv_safe(user.full_name),
            csv_safe(user.email), csv_safe(reg.event.name), csv_safe(reg.distance.name), reg.bib_number,
            reg.status.value, csv_safe(p.admin_note),
        ])
    return "\ufeff" + buf.getvalue(), f"payments-{start.isoformat()}-to-{end.isoformat()}.csv"


# ------------------------------------------------------------------ refunds
def _refund_joined(stmt):
    return (
        stmt.join(Registration, Registration.id == Refund.registration_id)
        .join(User, User.id == Refund.user_id)
        .join(Payment, Payment.id == Refund.payment_id)
    )


def _refund_out(db: Session, refund: Refund, reg: Registration, user: User, payment: Payment) -> AdminRefundOut:
    decider = db.get(User, refund.decided_by) if refund.decided_by else None
    return AdminRefundOut(
        id=refund.id, created_at=refund.created_at, decided_at=refund.decided_at,
        status=refund.status, reason=refund.reason, amount=refund.amount, phone=refund.phone,
        mpesa_reference=refund.mpesa_reference, admin_note=refund.admin_note,
        user=PersonOut(id=user.id, full_name=user.full_name, email=user.email),
        event=EventRef(id=reg.event.id, name=reg.event.name, event_date=reg.event.event_date),
        distance_name=reg.distance.name, bib_number=reg.bib_number, registration_id=reg.id,
        payment_id=payment.id, payment_receipt=payment.mpesa_receipt,
        decided_by_name=decider.full_name if decider else None,
    )


def list_refunds(
    db: Session, *, status: RefundStatus | None, q: str | None, page: int, page_size: int
) -> AdminRefundPage:
    conds = []
    if status:
        conds.append(Refund.status == status)
    if q and q.strip():
        like = f"%{q.strip()}%"
        conds.append(or_(
            User.email.ilike(like), User.full_name.ilike(like),
            Refund.phone.ilike(like), Refund.mpesa_reference.ilike(like),
        ))
    total = db.scalar(_refund_joined(select(func.count(Refund.id))).where(*conds)) or 0
    # A queue is worked oldest-first. Anything else reads newest-first.
    order = Refund.created_at.asc() if status == RefundStatus.requested else Refund.created_at.desc()
    rows = db.execute(
        _refund_joined(select(Refund, Registration, User, Payment))
        .where(*conds)
        .order_by(order)
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    return AdminRefundPage(items=[_refund_out(db, r, g, u, p) for r, g, u, p in rows], total=total)


def get_refund(db: Session, refund_id: uuid.UUID) -> AdminRefundDetail:
    row = db.execute(
        _refund_joined(select(Refund, Registration, User, Payment)).where(Refund.id == refund_id)
    ).first()
    if row is None:
        raise RefundError("refund_not_found", "Refund not found", 404)
    refund, reg, user, payment = row
    return AdminRefundDetail(**_refund_out(db, refund, reg, user, payment).model_dump(), audit=_audit(db, "refund", refund.id))