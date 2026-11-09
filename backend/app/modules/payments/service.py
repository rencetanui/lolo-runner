import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import hit
from app.modules.audit.service import log_action
from app.modules.auth.models import User
from app.modules.notifications import service as notifications
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.registrations.service import expire_stale
from app.modules.runners.models import RunnerProfile

from .models import Payment, PaymentStatus
from .providers.mpesa import MpesaError, MpesaProcessing
from .schemas import PaymentIn

log = logging.getLogger(__name__)

UNSENT_AFTER = timedelta(minutes=2)
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


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


# ---------------------------------------------------------------- reading callbacks
def _callback_metadata(payload) -> dict:
    try:
        items = (payload["Body"]["stkCallback"].get("CallbackMetadata") or {}).get("Item") or []
    except (KeyError, TypeError, AttributeError):
        return {}
    if not isinstance(items, list):
        return {}
    return {i.get("Name"): i.get("Value") for i in items if isinstance(i, dict)}


def _callback_code(payload) -> int | None:
    try:
        return int(payload["Body"]["stkCallback"]["ResultCode"])
    except (KeyError, TypeError, ValueError):
        return None


def _verify_enabled() -> bool:
    flag = settings.mpesa_verify_callbacks
    return (settings.mpesa_env == "production") if flag is None else flag


def _query_verdict(mpesa, checkout_request_id: str) -> int | None:
    """What Safaricom itself says about this request. None means it couldn't tell us (yet)."""
    try:
        data = mpesa.stk_query(checkout_request_id)
    except MpesaError:          # includes "still being processed"
        return None
    try:
        return int(data.get("ResultCode"))
    except (TypeError, ValueError, AttributeError):
        return None


# ---------------------------------------------------------------- recording outcomes
def _flag_review(db: Session, payment: Payment, reason: str, raw: dict | None = None) -> None:
    """Park a payment for a human: money may have moved, but we can't be sure it should count."""
    locked = db.scalars(select(Payment).where(Payment.id == payment.id).with_for_update()).first()
    if locked is None or locked.status != PaymentStatus.pending:
        return
    locked.status = PaymentStatus.needs_review
    locked.result_desc = reason[:255]
    locked.raw_callback = raw if raw is not None else locked.raw_callback
    locked.completed_at = _now()
    log.error("Payment %s flagged for review: %s", locked.id, reason)
    log_action(db, None, "payment.flagged", "payment", locked.id, reason=reason)
    notifications.notify_admins_payment_problem(db, locked, "needs_review", reason)
    db.commit()


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
            reason = f"Amount mismatch: expected KES {int(payment.amount)}, M-Pesa reported {paid}."
            payment.status = PaymentStatus.needs_review
            payment.result_desc = reason[:255]
            log.error("Payment %s: %s", payment.id, reason)
            log_action(db, None, "payment.flagged", "payment", payment.id, reason=reason)
            notifications.notify_admins_payment_problem(db, payment, "needs_review", reason)
            db.commit()
            return payment

    receipt = metadata.get("MpesaReceiptNumber")
    receipt = str(receipt) if receipt else None
    if receipt and db.scalar(
        select(func.count(Payment.id)).where(Payment.mpesa_receipt == receipt, Payment.id != payment.id)
    ):
        reason = f"M-Pesa receipt {receipt} is already recorded on another payment."
        payment.status = PaymentStatus.needs_review
        payment.result_desc = reason[:255]
        log.error("Payment %s: %s", payment.id, reason)
        log_action(db, None, "payment.flagged", "payment", payment.id, reason=reason)
        notifications.notify_admins_payment_problem(db, payment, "needs_review", reason)
        db.commit()
        return payment

    payment.status = PaymentStatus.succeeded
    payment.mpesa_receipt = receipt
    
    # of=Registration: only lock this table, not its eagerly-joined event/distance
    reg = db.scalars(
        select(Registration).where(Registration.id == payment.registration_id).with_for_update(of=Registration)
    ).first()
    if reg is None or reg.status == RegistrationStatus.cancelled:
        # The customer paid but the spot was released. Never lose track of that money.
        reason = "Payment received after the spot was released."
        payment.needs_refund = True
        log.error("Payment %s succeeded but its registration is cancelled: refund needed", payment.id)
        log_action(db, None, "payment.needs_refund", "payment", payment.id, reason=reason)
        notifications.notify_admins_payment_problem(db, payment, "needs_refund", reason)
    else:
        reg.status = RegistrationStatus.confirmed
        reg.expires_at = None
        notifications.notify_registration_confirmed(db, reg, payment)
    db.commit()
    return payment


def handle_stk_callback(db: Session, payload: dict, mpesa) -> None:
    try:
        cb = payload["Body"]["stkCallback"]
        checkout_id = str(cb["CheckoutRequestID"])
        code = int(cb["ResultCode"])
    except (KeyError, TypeError, ValueError):
        raise PaymentError("invalid_callback", "Malformed callback", 400)

    if code == 0 and _verify_enabled():
        payment = db.scalars(select(Payment).where(Payment.checkout_request_id == checkout_id)).first()
        if payment is not None and payment.status == PaymentStatus.pending:
            verdict = _query_verdict(mpesa, checkout_id)
            if verdict is None:
                # We can't confirm it with Safaricom right now. Keep the claim (with its receipt number)
                # and let the worker settle it shortly.
                payment.raw_callback = payload
                payment.result_desc = "Paid, according to the callback. Waiting for M-Pesa to confirm."
                db.commit()
                return
            if verdict != 0:
                _flag_review(
                    db, payment,
                    f"The callback reported success, but M-Pesa's own status check says code {verdict}.",
                    payload,
                )
                return

    apply_result(db, checkout_id, code, str(cb.get("ResultDesc") or ""), _callback_metadata(payload), payload)


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

    claimed = _callback_code(payment.raw_callback)
    if claimed == 0 and code != 0:
        _flag_review(
            db, payment,
            f"A callback reported success, but M-Pesa's own status check now says code {code}.",
            payment.raw_callback,
        )
        return
    stored = payment.raw_callback if claimed is not None else None      # keeps the callback's receipt number
    apply_result(
        db, payment.checkout_request_id, code, str(data.get("ResultDesc") or ""),
        _callback_metadata(stored), stored or data,
    )


def check_payment(db: Session, user: User, payment_id: uuid.UUID, mpesa) -> Payment:
    payment = _owned_payment(db, user, payment_id)
    if payment.status == PaymentStatus.pending and payment.checkout_request_id:
        _refresh(db, payment, mpesa)
        db.refresh(payment)
    return payment


def recheck_payment(db: Session, payment_id: uuid.UUID, mpesa) -> Payment:
    """Admin version of check_payment: any payment, not just your own."""
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise PaymentError("payment_not_found", "Payment not found", 404)
    if payment.status == PaymentStatus.pending and payment.checkout_request_id:
        _refresh(db, payment, mpesa)
        db.refresh(payment)
    return payment


# ---------------------------------------------------------------- an admin decides
def resolve_review(
    db: Session, admin: User, payment_id: uuid.UUID, action: str, note: str, receipt: str | None = None
) -> Payment:
    payment = db.scalars(select(Payment).where(Payment.id == payment_id).with_for_update()).first()
    if payment is None:
        raise PaymentError("payment_not_found", "Payment not found", 404)
    if payment.status != PaymentStatus.needs_review:
        raise PaymentError("not_in_review", "Only payments waiting for review can be resolved.", 409)

    payment.admin_note = note.strip()[:500]
    payment.resolved_at = _now()
    if action == "dismiss":
        payment.status = PaymentStatus.failed
        log_action(db, admin, "payment.dismissed", "payment", payment.id, note=payment.admin_note)
    else:
        payment.status = PaymentStatus.succeeded
        if receipt:
            payment.mpesa_receipt = receipt
        try:
            db.flush()    # a duplicate receipt surfaces here
        except IntegrityError:
            db.rollback()
            raise PaymentError("duplicate_receipt", "That M-Pesa reference is already recorded on another payment.", 409)
        reg = db.scalars(
            select(Registration).where(Registration.id == payment.registration_id).with_for_update(of=Registration)
        ).first()
        if reg is None or reg.status == RegistrationStatus.cancelled:
            payment.needs_refund = True
        else:
            reg.status = RegistrationStatus.confirmed
            reg.expires_at = None
            notifications.notify_registration_confirmed(db, reg, payment)
        log_action(
            db, admin, "payment.confirmed", "payment", payment.id,
            note=payment.admin_note, receipt=payment.mpesa_receipt, needs_refund=payment.needs_refund,
        )
    db.commit()
    return payment


# ---------------------------------------------------------------- starting a payment
def _resolve_phone(db: Session, user: User, data: PaymentIn) -> tuple[str, bool]:
    """The number to prompt, and whether it's the runner's own profile number."""
    profile = db.scalars(select(RunnerProfile).where(RunnerProfile.user_id == user.id)).first()
    own = profile.phone if profile else None
    phone = data.phone or own
    if not phone:
        raise PaymentError("phone_required", "Enter the M-Pesa number you want to pay with.", 422)
    if not phone.startswith("+254"):
        raise PaymentError("kenyan_number_required", "M-Pesa payments need a Kenyan (+254) phone number.", 422)
    return phone, phone == own


def start_payment(
    db: Session, user: User, registration_id: uuid.UUID, data: PaymentIn, mpesa, ip: str = "unknown"
) -> Payment:
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

    phone, is_own = _resolve_phone(db, user, data)

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

    # Abuse limits. These only count real attempts, so clicking while a prompt is live costs nothing.
    hit(db, "stk:user", str(user.id), limit=5, window=HOUR)
    hit(db, "stk:ip", ip, limit=30, window=HOUR)
    if not is_own:
        # Prompting someone else's phone is the harassment risk, so it's capped per number and per user.
        hit(db, "stk:phone", phone, limit=3, window=HOUR)
        hit(db, "stk:other", str(user.id), limit=3, window=DAY)

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


def reconcile_pending(db: Session, mpesa, *, older_than: timedelta = timedelta(minutes=2), limit: int = 50) -> dict:
    """Worker job: settle payments whose callback never arrived. Commits."""
    cutoff = _now() - older_than
    abandoned = db.execute(
        update(Payment)
        .where(
            Payment.status == PaymentStatus.pending,
            Payment.checkout_request_id.is_(None),
            Payment.created_at < cutoff,
        )
        .values(status=PaymentStatus.failed, result_desc="Request never reached M-Pesa", completed_at=_now())
    ).rowcount
    db.commit()

    stuck = list(
        db.scalars(
            select(Payment)
            .where(
                Payment.status == PaymentStatus.pending,
                Payment.checkout_request_id.is_not(None),
                Payment.created_at < cutoff,
            )
            .order_by(Payment.created_at)
            .limit(limit)
        )
    )
    settled = 0
    for payment in stuck:
        _refresh(db, payment, mpesa)
        db.refresh(payment)
        if payment.status != PaymentStatus.pending:
            settled += 1
    return {"abandoned": abandoned or 0, "settled": settled}