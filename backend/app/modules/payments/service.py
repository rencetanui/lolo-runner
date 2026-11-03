import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.models import User
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.registrations.service import expire_stale
from app.modules.runners.models import RunnerProfile

from .models import Payment, PaymentStatus
from .providers.mpesa import MpesaError, MpesaProcessing
from .schemas import PaymentIn

log = logging.getLogger(__name__)

UNSENT_AFTER = timedelta(minutes=2)


class PaymentError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- lookups
def _owned_registration(db: Session, user: User, registration_id: uuid.UUID) -> Registration:
    reg = db.get(Registration, registration_id)
    if not reg or reg.user_id != user.id:
        raise PaymentError("registration_not_found", "Registration not found", 404)
    return reg


def _owned_payment(db: Session, user: User, payment_id: uuid.UUID) -> Payment:
    payment = db.get(Payment, payment_id)
    if not payment or payment.user_id != user.id:
        raise PaymentError("payment_not_found", "Payment not found", 404)
    return payment


def list_for_registration(db: Session, user: User, registration_id: uuid.UUID) -> list[Payment]:
    _owned_registration(db, user, registration_id)
    return list(
        db.scalars(
            select(Payment)
            .where(Payment.registration_id == registration_id)
            .order_by(Payment.created_at.desc())
        )
    )


# ---------------------------------------------------------------- applying a result
def apply_result(
    db: Session,
    checkout_request_id: str,
    result_code: int,
    result_desc: str,
    metadata: dict,
    raw: dict,
) -> Payment | None:
    """Idempotently record the outcome of an STK Push. Used by the callback and by STK Query."""
    payment = db.scalars(
        select(Payment).where(Payment.checkout_request_id == checkout_request_id).with_for_update()
    ).first()
    if payment is None:
        log.warning("Callback for unknown CheckoutRequestID %s", checkout_request_id)
        return None
    if payment.status != PaymentStatus.pending:
        return payment    # duplicate or late callback: already handled

    payment.result_code = result_code
    payment.result_desc = result_desc[:255]
    payment.raw_callback = raw
    payment.completed_at = _now()

    if result_code != 0:
        payment.status = PaymentStatus.failed
        db.commit()
        return payment

    paid = metadata.get("Amount")
    if paid is not None:
        try:
            mismatch = Decimal(str(paid)) != payment.amount
        except InvalidOperation:
            mismatch = True
        if mismatch:
            payment.status = PaymentStatus.needs_review
            log.error("Amount mismatch on payment %s: expected %s, got %s", payment.id, payment.amount, paid)
            db.commit()
            return payment

    payment.status = PaymentStatus.succeeded
    receipt = metadata.get("MpesaReceiptNumber")
    payment.mpesa_receipt = str(receipt) if receipt else None

    # of=Registration: only lock this table, not its eagerly-joined event/distance
    reg = db.scalars(
        select(Registration).where(Registration.id == payment.registration_id).with_for_update(of=Registration)
    ).first()
    if reg is None or reg.status == RegistrationStatus.cancelled:
        # The customer paid but the spot was released. Never lose track of that money.
        payment.needs_refund = True
        log.error("Payment %s succeeded but its registration is cancelled: refund needed", payment.id)
    else:
        reg.status = RegistrationStatus.confirmed
        reg.expires_at = None
    db.commit()
    return payment


def handle_stk_callback(db: Session, payload: dict) -> None:
    try:
        cb = payload["Body"]["stkCallback"]
        checkout_id = str(cb["CheckoutRequestID"])
        code = int(cb["ResultCode"])
    except (KeyError, TypeError, ValueError):
        raise PaymentError("invalid_callback", "Malformed callback", 400)

    items = (cb.get("CallbackMetadata") or {}).get("Item") or []
    metadata = {i.get("Name"): i.get("Value") for i in items if isinstance(i, dict)} if isinstance(items, list) else {}
    apply_result(db, checkout_id, code, str(cb.get("ResultDesc") or ""), metadata, payload)


# ---------------------------------------------------------------- asking Safaricom directly
def _refresh(db: Session, payment: Payment, mpesa) -> None:
    try:
        data = mpesa.stk_query(payment.checkout_request_id)
    except MpesaProcessing:
        return
    except MpesaError as exc:
        log.warning("STK query failed for payment %s: %s", payment.id, exc)
        return
    try:
        code = int(data.get("ResultCode"))
    except (TypeError, ValueError):
        return    # no verdict yet
    apply_result(db, payment.checkout_request_id, code, str(data.get("ResultDesc") or ""), {}, data)


def check_payment(db: Session, user: User, payment_id: uuid.UUID, mpesa) -> Payment:
    payment = _owned_payment(db, user, payment_id)
    if payment.status == PaymentStatus.pending and payment.checkout_request_id:
        _refresh(db, payment, mpesa)
        db.refresh(payment)
    return payment


# ---------------------------------------------------------------- starting a payment
def _resolve_phone(db: Session, user: User, data: PaymentIn) -> str:
    phone = data.phone
    if not phone:
        profile = db.scalars(select(RunnerProfile).where(RunnerProfile.user_id == user.id)).first()
        phone = profile.phone if profile else None
    if not phone:
        raise PaymentError("phone_required", "Enter the M-Pesa number you want to pay with.", 422)
    if not phone.startswith("+254"):
        raise PaymentError("kenyan_number_required", "M-Pesa payments need a Kenyan (+254) phone number.", 422)
    return phone


def start_payment(db: Session, user: User, registration_id: uuid.UUID, data: PaymentIn, mpesa) -> Payment:
    expire_stale(db, user_id=user.id)
    db.commit()
    reg = _owned_registration(db, user, registration_id)

    if reg.status == RegistrationStatus.confirmed:
        raise PaymentError("already_paid", "This registration is already confirmed.")
    if reg.status == RegistrationStatus.cancelled:
        raise PaymentError(
            "hold_expired",
            "This registration was cancelled or its spot hold expired. Please register again.",
        )

    amount = reg.fee_amount
    if amount < 1 or amount != amount.to_integral_value():
        raise PaymentError("invalid_amount", "This entry fee can't be paid through M-Pesa. Please contact the organizers.", 422)

    phone = _resolve_phone(db, user, data)

    # Prompts that never reached M-Pesa (e.g. the server died mid-request) must not block retries.
    db.execute(
        update(Payment)
        .where(
            Payment.registration_id == reg.id,
            Payment.status == PaymentStatus.pending,
            Payment.checkout_request_id.is_(None),
            Payment.created_at < _now() - UNSENT_AFTER,
        )
        .values(status=PaymentStatus.failed, result_desc="Request never reached M-Pesa", completed_at=_now())
    )
    db.commit()

    # An earlier prompt may still be live, or may have been answered without us hearing.
    # Ask Safaricom before sending a second prompt, so nobody gets charged twice.
    open_payment = db.scalars(
        select(Payment).where(Payment.registration_id == reg.id, Payment.status == PaymentStatus.pending)
    ).first()
    if open_payment:
        if open_payment.checkout_request_id:
            _refresh(db, open_payment, mpesa)
            db.refresh(open_payment)
            db.refresh(reg)
        if reg.status == RegistrationStatus.confirmed:
            raise PaymentError("already_paid", "This registration is already confirmed.")
        if open_payment.status == PaymentStatus.pending:
            raise PaymentError(
                "payment_in_progress",
                "A payment prompt is already waiting on your phone. Approve it, or wait a minute and try again.",
            )

    payment = Payment(
        registration_id=reg.id,
        user_id=user.id,
        amount=amount,
        phone=phone,
        status=PaymentStatus.pending,
    )
    db.add(payment)
    # Keep the spot while the customer pays.
    reg.expires_at = _now() + timedelta(minutes=settings.registration_hold_minutes)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise PaymentError("payment_in_progress", "A payment is already in progress for this registration.")

    # No database locks are held during the network call.
    try:
        resp = mpesa.stk_push(
            phone=phone.lstrip("+"),
            amount=int(amount),
            reference=f"BIB{reg.bib_number}",
            description="Race entry",
        )
    except MpesaError as exc:
        log.warning("STK push failed for payment %s: %s", payment.id, exc)
        payment.status = PaymentStatus.failed
        payment.result_desc = str(exc)[:255]
        payment.completed_at = _now()
        db.commit()
        raise PaymentError("provider_unavailable", "We couldn't reach M-Pesa. Please try again in a moment.", 502)

    payment.merchant_request_id = resp.get("MerchantRequestID")
    payment.checkout_request_id = resp["CheckoutRequestID"]
    db.commit()
    return payment