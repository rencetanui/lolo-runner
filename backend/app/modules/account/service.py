import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.rate_limit import hit
from app.core.security import hash_password
from app.modules.audit.service import log_action
from app.modules.auth import service as auth_service
from app.modules.auth.models import AuthToken, Role, TokenPurpose, User, UserIdentity
from app.modules.events.models import Event
from app.modules.notifications import service as notifications
from app.modules.notifications.models import Notification
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.refunds.models import Refund, RefundStatus
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.runners.models import RunnerProfile
from app.modules.support.models import SupportMessage
from app.utils.dates import today_ke

log = logging.getLogger(__name__)

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
DELETE_LINK_MINUTES = 60


class AccountError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


# ---------------------------------------------------------------- download my data
def export_data(db: Session, user: User) -> dict:
    profile = db.scalars(select(RunnerProfile).where(RunnerProfile.user_id == user.id)).first()
    regs = db.scalars(
        select(Registration).where(Registration.user_id == user.id).order_by(Registration.created_at)
    ).unique().all()
    payments = db.scalars(select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at)).all()
    refunds = db.scalars(select(Refund).where(Refund.user_id == user.id).order_by(Refund.created_at)).all()
    messages = db.scalars(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at)
    ).all()
    support = db.scalars(
        select(SupportMessage).where(SupportMessage.user_id == user.id).order_by(SupportMessage.created_at)
    ).all()
    google = (db.scalar(select(func.count(UserIdentity.id)).where(UserIdentity.user_id == user.id)) or 0) > 0

    return {
        "exported_at": _now().isoformat(),
        "format_version": 1,
        "notes": (
            "This file contains the personal data we hold about you. Passwords are stored only as one-way hashes "
            "and are not included, and neither are internal administrative records."
        ),
        "account": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "created_at": _iso(user.created_at),
            "email_verified_at": _iso(user.email_verified_at),
            "has_password": user.has_password,
            "signs_in_with_google": google,
            "accepted_terms_version": user.legal_version,
            "accepted_terms_at": _iso(user.legal_accepted_at),
        },
        "runner_profile": None if profile is None else {
            "date_of_birth": profile.date_of_birth.isoformat(),
            "gender": profile.gender.value,
            "phone": profile.phone,
            "county": profile.county,
            "club": profile.club,
            "tshirt_size": profile.tshirt_size.value,
            "emergency_contact_name": profile.emergency_contact_name,
            "emergency_contact_phone": profile.emergency_contact_phone,
            "emergency_contact_relationship": profile.emergency_contact_relationship,
            "medical_notes": profile.medical_notes,
        },
        "registrations": [
            {
                "id": str(r.id),
                "event_name": r.event.name,
                "event_date": r.event.event_date.isoformat(),
                "distance": r.distance.name,
                "bib_number": r.bib_number,
                "status": r.status.value,
                "entry_fee_kes": int(r.fee_amount),
                "estimated_finish_minutes": r.estimated_finish_minutes,
                "waiver_version": r.waiver_version,
                "waiver_accepted_at": _iso(r.waiver_accepted_at),
                "guardian_consent": r.guardian_consent,
                "registered_at": _iso(r.created_at),
                "cancelled_at": _iso(r.cancelled_at),
            }
            for r in regs
        ],
        "payments": [
            {
                "id": str(p.id),
                "registration_id": str(p.registration_id),
                "amount_kes": int(p.amount),
                "phone": p.phone,
                "status": p.status.value,
                "mpesa_receipt": p.mpesa_receipt,
                "started_at": _iso(p.created_at),
                "completed_at": _iso(p.completed_at),
            }
            for p in payments
        ],
        "refunds": [
            {
                "id": str(f.id),
                "payment_id": str(f.payment_id),
                "amount_kes": int(f.amount),
                "phone": f.phone,
                "reason": f.reason.value,
                "status": f.status.value,
                "mpesa_reference": f.mpesa_reference,
                "requested_at": _iso(f.created_at),
                "decided_at": _iso(f.decided_at),
            }
            for f in refunds
        ],
        "messages_sent_to_you": [
            {
                "channel": n.channel.value,
                "to_address": n.to_address,
                "subject": n.subject,
                "status": n.status.value,
                "queued_at": _iso(n.created_at),
                "sent_at": _iso(n.sent_at),
            }
            for n in messages
        ],
        "support_messages": [
            {"sent_at": _iso(m.created_at), "topic": m.topic.value, "message": m.message, "status": m.status.value}
            for m in support
        ],
    }


def export_for_download(db: Session, user: User) -> dict:
    hit(db, "export:user", str(user.id), limit=3, window=DAY)
    data = export_data(db, user)
    log_action(db, user, "account.exported", "user", user.id)
    notifications.notify_data_exported(db, user)
    db.commit()
    return data


# ---------------------------------------------------------------- change my name
def update_name(db: Session, user: User, full_name: str) -> User:
    user.full_name = full_name
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------- delete my account
def deletion_blockers(db: Session, user: User) -> list[dict]:
    blockers: list[dict] = []
    if user.role != Role.runner:
        blockers.append({
            "code": "role",
            "message": "Organizer and admin accounts can't be deleted here. Ask an admin to switch your account "
                       "to a runner account first.",
        })
    upcoming = db.execute(
        select(Event.name)
        .join(Registration, Registration.event_id == Event.id)
        .where(
            Registration.user_id == user.id,
            Registration.status == RegistrationStatus.confirmed,
            Event.event_date >= today_ke(),
        )
        .order_by(Event.event_date)
    ).scalars().all()
    if upcoming:
        blockers.append({
            "code": "upcoming_registrations",
            "message": f"You're registered for {len(upcoming)} upcoming event(s): {', '.join(upcoming)}. "
                       "Cancel those registrations first.",
        })
    open_payments = db.scalar(
        select(func.count(Payment.id)).where(
            Payment.user_id == user.id,
            or_(
                Payment.status.in_([PaymentStatus.pending, PaymentStatus.needs_review]),
                Payment.needs_refund.is_(True),
            ),
        )
    ) or 0
    open_refunds = db.scalar(
        select(func.count(Refund.id)).where(Refund.user_id == user.id, Refund.status == RefundStatus.requested)
    ) or 0
    if open_payments or open_refunds:
        blockers.append({
            "code": "money_open",
            "message": "A payment or refund involving you is still being processed. You can delete your account "
                       "once it has been completed.",
        })
    return blockers


def request_deletion(db: Session, user: User) -> None:
    blockers = deletion_blockers(db, user)
    if blockers:
        raise AccountError("deletion_blocked", blockers[0]["message"], 409)
    hit(db, "delete_request:user", str(user.id), limit=3, window=HOUR)
    raw, row = auth_service.issue_token(db, user, TokenPurpose.account_delete, timedelta(minutes=DELETE_LINK_MINUTES))
    notifications.notify_account_deletion(db, user, raw, row.id, DELETE_LINK_MINUTES)
    log_action(db, user, "account.deletion_requested", "user", user.id)
    db.commit()


def _mask_phone(phone: str) -> str:
    return phone[:4] + "*" * (len(phone) - 7) + phone[-3:] if len(phone) > 7 else "***"


def confirm_deletion(db: Session, user: User, raw_token: str) -> None:
    token = auth_service.usable_token(db, raw_token, TokenPurpose.account_delete)
    if token is None or token.user_id != user.id:
        raise AccountError("invalid_token", "This deletion link is invalid or has expired. Please request a new one.", 400)
    blockers = deletion_blockers(db, user)
    if blockers:
        raise AccountError("deletion_blocked", blockers[0]["message"], 409)

    old_email, old_name, now = user.email, user.full_name, _now()

    # 1. Unpaid reservations hold no money, so just release the spots.
    db.execute(
        update(Registration)
        .where(Registration.user_id == user.id, Registration.status == RegistrationStatus.pending_payment)
        .values(status=RegistrationStatus.cancelled, cancelled_at=now)
    )

    # 2. Financial records stay, without contact details.
    for payment in db.scalars(select(Payment).where(Payment.user_id == user.id)):
        payment.phone = _mask_phone(payment.phone)
        payment.raw_callback = None
    for refund in db.scalars(select(Refund).where(Refund.user_id == user.id)):
        refund.phone = _mask_phone(refund.phone)

    # 3. Everything personal goes. Copies of this person's messages that were emailed to admins go too.
    for message_id in db.scalars(select(SupportMessage.id).where(SupportMessage.user_id == user.id)):
        db.execute(delete(Notification).where(Notification.dedupe_key.like(f"support_alert:{message_id}:%")))
    db.execute(delete(SupportMessage).where(SupportMessage.user_id == user.id))
    db.execute(delete(Notification).where(Notification.user_id == user.id))
    db.execute(delete(RunnerProfile).where(RunnerProfile.user_id == user.id))
    db.execute(delete(UserIdentity).where(UserIdentity.user_id == user.id))
    db.execute(delete(AuthToken).where(AuthToken.user_id == user.id))

    # 4. The account row stays, anonymous, so payments, refunds and audit entries keep their links.
    user.email = f"deleted-{user.id.hex}@deleted.invalid"
    user.full_name = "Deleted user"
    user.hashed_password = hash_password(secrets.token_urlsafe(32))
    user.has_password = False
    user.is_active = False
    user.email_verified_at = None
    user.token_version += 1                  # ends every session
    user.deleted_at = now

    log_action(db, user, "account.deleted", "user", user.id)
    notifications.notify_account_deleted(db, old_email, old_name)
    db.commit()
    log.info("account deleted user=%s", user.id)