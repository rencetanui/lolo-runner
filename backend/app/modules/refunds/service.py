import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.audit.service import log_action
from app.modules.auth.models import User
from app.modules.notifications import service as notifications
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.registrations.models import Registration, RegistrationStatus
from app.utils.dates import today_ke

from .models import Refund, RefundReason, RefundStatus

log = logging.getLogger(__name__)


class RefundError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _active_refund(db: Session, payment_id: uuid.UUID) -> Refund | None:
    return db.scalars(
        select(Refund).where(Refund.payment_id == payment_id, Refund.status != RefundStatus.rejected)
    ).first()


def _succeeded_payment(db: Session, registration_id: uuid.UUID) -> Payment | None:
    return db.scalars(
        select(Payment)
        .where(Payment.registration_id == registration_id, Payment.status == PaymentStatus.succeeded)
        .order_by(Payment.completed_at.desc())
    ).first()


def _new_refund(db: Session, payment: Payment, reason: RefundReason, actor: User | None, notify: bool) -> Refund:
    refund = Refund(
        id=uuid.uuid4(),
        payment_id=payment.id,
        registration_id=payment.registration_id,
        user_id=payment.user_id,
        amount=payment.amount,
        phone=payment.phone,
        reason=reason,
        status=RefundStatus.requested,
    )
    db.add(refund)
    log_action(db, actor, "refund.requested", "refund", refund.id, reason=reason.value, amount=int(payment.amount))
    if notify:
        notifications.notify_refund_requested(db, refund)
    return refund


# ---------------------------------------------------------------- created by cancellations
def refund_for_runner_cancellation(db: Session, reg: Registration, *, was_paid: bool, actor: User) -> Refund | None:
    """A runner cancelled. Refund in full if the event's refund window is still open."""
    if not was_paid or reg.fee_amount <= 0:
        return None
    until = reg.event.refunds_until
    if until is None or today_ke() > until:
        return None
    payment = _succeeded_payment(db, reg.id)
    if payment is None or _active_refund(db, payment.id):
        return None
    # No separate email: the cancellation email already explains the refund.
    return _new_refund(db, payment, RefundReason.runner_cancelled, actor, notify=False)


def refund_for_event_cancellation(db: Session, reg: Registration, *, was_paid: bool, actor: User) -> Refund | None:
    """The organizers cancelled the whole event: everyone who paid gets a full refund, whatever the policy."""
    if not was_paid or reg.fee_amount <= 0:
        return None
    payment = _succeeded_payment(db, reg.id)
    if payment is None or _active_refund(db, payment.id):
        return None
    return _new_refund(db, payment, RefundReason.event_cancelled, actor, notify=False)


# ---------------------------------------------------------------- what runners see
def _owned_registration(db: Session, user: User, registration_id: uuid.UUID) -> Registration:
    reg = db.get(Registration, registration_id)
    if not reg or reg.user_id != user.id:
        raise RefundError("registration_not_found", "Registration not found", 404)
    return reg


def cancellation_preview(db: Session, user: User, registration_id: uuid.UUID) -> dict:
    reg = _owned_registration(db, user, registration_id)
    paid = reg.status == RegistrationStatus.confirmed and reg.fee_amount > 0
    until = reg.event.refunds_until
    refundable = bool(paid and until is not None and today_ke() <= until)
    return {
        "paid": paid,
        "refundable": refundable,
        "amount": reg.fee_amount if refundable else None,
        "refunds_until": until,
    }


def latest_refund(db: Session, user: User, registration_id: uuid.UUID) -> Refund | None:
    _owned_registration(db, user, registration_id)
    return db.scalars(
        select(Refund).where(Refund.registration_id == registration_id).order_by(Refund.created_at.desc())
    ).first()


# ---------------------------------------------------------------- what admins do
def create_admin_refund(db: Session, admin: User, payment_id: uuid.UUID, note: str) -> Refund:
    payment = db.scalars(select(Payment).where(Payment.id == payment_id).with_for_update()).first()
    if payment is None:
        raise RefundError("payment_not_found", "Payment not found", 404)
    if payment.status != PaymentStatus.succeeded:
        raise RefundError("payment_not_paid", "Only payments that succeeded can be refunded.", 409)
    if _active_refund(db, payment.id):
        raise RefundError("already_refunding", "This payment already has a refund.", 409)

    late = payment.needs_refund
    refund = _new_refund(db, payment, RefundReason.late_payment if late else RefundReason.admin, admin, notify=True)
    refund.admin_note = note.strip()[:500]
    if late:
        payment.needs_refund = False        # now tracked by the refund instead
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise RefundError("already_refunding", "This payment already has a refund.", 409)
    return refund


def _locked_requested(db: Session, refund_id: uuid.UUID) -> Refund:
    refund = db.scalars(select(Refund).where(Refund.id == refund_id).with_for_update()).first()
    if refund is None:
        raise RefundError("refund_not_found", "Refund not found", 404)
    if refund.status != RefundStatus.requested:
        raise RefundError("not_requested", "Only requested refunds can be updated.", 409)
    return refund


def mark_paid(db: Session, admin: User, refund_id: uuid.UUID, reference: str, note: str | None) -> Refund:
    """The admin has sent the money by M-Pesa and is recording the transaction code."""
    refund = _locked_requested(db, refund_id)
    refund.status = RefundStatus.paid
    refund.mpesa_reference = reference.strip().upper()
    refund.admin_note = (note or "").strip()[:500] or None
    refund.decided_by = admin.id
    refund.decided_at = _now()
    try:
        db.flush()        # a duplicate reference surfaces here, before anything else touches the session
    except IntegrityError:
        db.rollback()
        raise RefundError("duplicate_reference", "That M-Pesa reference is already recorded on another refund.", 409)
    log_action(db, admin, "refund.paid", "refund", refund.id, reference=refund.mpesa_reference, amount=int(refund.amount))
    notifications.notify_refund_paid(db, refund)
    db.commit()
    return refund


def reject(db: Session, admin: User, refund_id: uuid.UUID, note: str) -> Refund:
    refund = _locked_requested(db, refund_id)
    refund.status = RefundStatus.rejected
    refund.admin_note = note.strip()[:500]
    refund.decided_by = admin.id
    refund.decided_at = _now()
    if refund.reason == RefundReason.late_payment:
        # The money is still sitting there with no spot behind it: put it back on the attention list.
        payment = db.get(Payment, refund.payment_id)
        if payment is not None:
            payment.needs_refund = True
    log_action(db, admin, "refund.rejected", "refund", refund.id, note=refund.admin_note)
    notifications.notify_refund_rejected(db, refund)
    db.commit()
    return refund