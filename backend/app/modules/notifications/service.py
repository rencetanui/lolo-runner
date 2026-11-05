import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.models import User
from app.modules.events.models import Event, EventStatus
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.runners.models import RunnerProfile
from app.utils.dates import KENYA_TZ

from . import templates
from .models import Channel, Notification, NotificationStatus
from .providers.base import PermanentSendError

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BACKOFF = [timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15), timedelta(minutes=60)]
LEASE = timedelta(minutes=5)
KEY_CHUNK = 500
CHANGE_LABELS = {"event_date": "Date", "location": "Location"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _url(path: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}{path}"


def _fmt(value) -> str:
    return templates.fmt_date(value) if isinstance(value, date) else str(value)


# ----------------------------------------------------------------- queueing
# These functions only add rows to the caller's transaction. The caller commits, so a message
# exists if and only if the change that caused it was saved.
def _items(
    user: User, profile: RunnerProfile | None, rendered: templates.Rendered, key: str, sensitive: bool = False
) -> list[dict]:
    items = [{
        "user_id": user.id, "channel": Channel.email, "to": user.email,
        "subject": rendered.subject, "text": rendered.text, "html": rendered.html,
        "key": f"{key}:email", "sensitive": sensitive,
    }]
    if rendered.sms and profile and profile.phone:
        items.append({
            "user_id": user.id, "channel": Channel.sms, "to": profile.phone,
            "subject": None, "text": rendered.sms, "html": None,
            "key": f"{key}:sms", "sensitive": sensitive,
        })
    return items


def _enqueue_many(db: Session, items: list[dict]) -> int:
    added = 0
    for start in range(0, len(items), KEY_CHUNK):
        chunk = items[start:start + KEY_CHUNK]
        existing = set(
            db.scalars(select(Notification.dedupe_key).where(Notification.dedupe_key.in_([i["key"] for i in chunk])))
        )
        for i in chunk:
            if i["key"] in existing:
                continue
            db.add(Notification(
                user_id=i["user_id"],
                channel=i["channel"],
                to_address=i["to"],
                subject=" ".join(i["subject"].split())[:190] if i["subject"] else None,
                body_text=i["text"],
                body_html=i["html"],
                dedupe_key=i["key"],
                sensitive=i.get("sensitive", False),
            ))
            added += 1
    return added


def _contact(db: Session, user_id: uuid.UUID) -> tuple[User, RunnerProfile | None]:
    user = db.get(User, user_id)
    profile = db.scalars(select(RunnerProfile).where(RunnerProfile.user_id == user_id)).first()
    return user, profile


def notify_registration_confirmed(db: Session, reg: Registration, payment=None) -> None:
    try:
        user, profile = _contact(db, reg.user_id)
        rendered = templates.registration_confirmed(
            name=user.full_name,
            event_name=reg.event.name,
            event_date=reg.event.event_date,
            location=reg.event.location,
            distance=reg.distance.name,
            bib=reg.bib_number,
            url=_url(f"/registrations/{reg.id}"),
            amount=payment.amount if payment else None,
            receipt=payment.mpesa_receipt if payment else None,
        )
        _enqueue_many(db, _items(user, profile, rendered, f"registration_confirmed:{reg.id}"))
    except Exception:
        # A notification problem must never undo a confirmed payment or registration.
        log.exception("Could not queue the confirmation for registration %s", reg.id)


def notify_registration_cancelled(db: Session, reg: Registration) -> None:
    try:
        user, profile = _contact(db, reg.user_id)
        rendered = templates.registration_cancelled(
            name=user.full_name,
            event_name=reg.event.name,
            distance=reg.distance.name,
            url=_url(f"/events/{reg.event_id}"),
        )
        _enqueue_many(db, _items(user, profile, rendered, f"registration_cancelled:{reg.id}"))
    except Exception:
        log.exception("Could not queue the cancellation notice for registration %s", reg.id)


def notify_event_changed(db: Session, event: Event, changes: dict) -> None:
    """Tell everyone registered (or holding a spot) about a new date or location."""
    try:
        shown = [(CHANGE_LABELS[k], _fmt(old), _fmt(new)) for k, (old, new) in changes.items() if k in CHANGE_LABELS]
        if not shown:
            return
        batch = uuid.uuid4().hex[:12]
        rows = db.execute(
            select(Registration, User, RunnerProfile)
            .join(User, User.id == Registration.user_id)
            .outerjoin(RunnerProfile, RunnerProfile.user_id == Registration.user_id)
            .where(Registration.event_id == event.id, Registration.status != RegistrationStatus.cancelled)
        ).all()
        items: list[dict] = []
        for reg, user, profile in rows:
            rendered = templates.event_changed(
                name=user.full_name, event_name=event.name, changes=shown,
                url=_url(f"/registrations/{reg.id}"),
            )
            items += _items(user, profile, rendered, f"event_changed:{batch}:{reg.id}")
        log.info("Queued %s notifications for the update to event %s", _enqueue_many(db, items), event.id)
    except Exception:
        log.exception("Could not queue the update notices for event %s", event.id)


def notify_email_verification(db: Session, user: User, token: str, token_id: uuid.UUID, hours: int) -> None:
    try:
        rendered = templates.email_verification(
            name=user.full_name, url=_url(f"/verify-email?token={token}"), hours=hours
        )
        _enqueue_many(db, _items(user, None, rendered, f"email_verify:{token_id}", sensitive=True))
    except Exception:
        log.exception("Could not queue the verification email for user %s", user.id)


def notify_password_reset(db: Session, user: User, token: str, token_id: uuid.UUID, minutes: int) -> None:
    try:
        rendered = templates.password_reset(
            name=user.full_name, url=_url(f"/reset-password?token={token}"), minutes=minutes
        )
        _enqueue_many(db, _items(user, None, rendered, f"password_reset:{token_id}", sensitive=True))
    except Exception:
        log.exception("Could not queue the password reset email for user %s", user.id)


def notify_password_changed(db: Session, user: User) -> None:
    try:
        rendered = templates.password_changed(name=user.full_name, url=_url("/forgot-password"))
        _enqueue_many(db, _items(user, None, rendered, f"password_changed:{uuid.uuid4().hex}"))
    except Exception:
        log.exception("Could not queue the password-changed notice for user %s", user.id)

def notify_google_linked(db: Session, user: User) -> None:
    try:
        rendered = templates.google_linked(name=user.full_name, url=_url("/forgot-password"))
        _enqueue_many(db, _items(user, None, rendered, f"google_linked:{uuid.uuid4().hex}"))
    except Exception:
        log.exception("Could not queue the Google-linked notice for user %s", user.id)
        
def enqueue_event_reminders(db: Session, now: datetime | None = None) -> int:
    """Worker job: queue "it's tomorrow" reminders. Commits.

    Only runs between 08:00 and 20:00 Nairobi time, and dedupe keys make it safe to run often.
    """
    now_ke = (now or datetime.now(KENYA_TZ)).astimezone(KENYA_TZ)
    if not 8 <= now_ke.hour < 20:
        return 0
    tomorrow = now_ke.date() + timedelta(days=1)
    rows = db.execute(
        select(Registration, User, RunnerProfile, Event)
        .join(Event, Event.id == Registration.event_id)
        .join(User, User.id == Registration.user_id)
        .outerjoin(RunnerProfile, RunnerProfile.user_id == Registration.user_id)
        .where(
            Event.event_date == tomorrow,
            Event.status == EventStatus.published,
            Registration.status == RegistrationStatus.confirmed,
        )
    ).all()
    items: list[dict] = []
    for reg, user, profile, event in rows:
        rendered = templates.event_reminder(
            name=user.full_name, event_name=event.name, event_date=event.event_date,
            location=event.location, distance=reg.distance.name, bib=reg.bib_number,
            url=_url(f"/registrations/{reg.id}"),
        )
        items += _items(user, profile, rendered, f"reminder:{reg.id}:{event.event_date.isoformat()}")
    try:
        added = _enqueue_many(db, items)
        db.commit()
    except IntegrityError:       # another worker queued the same reminders a moment ago
        db.rollback()
        return 0
    return added


# ----------------------------------------------------------------- delivery
def claim_due(db: Session, now: datetime, limit: int) -> list[uuid.UUID]:
    """Mark due messages as 'sending' with a lease, so several workers never take the same one."""
    due = or_(
        and_(Notification.status == NotificationStatus.pending, Notification.next_attempt_at <= now),
        and_(Notification.status == NotificationStatus.sending, Notification.lease_until < now),
    )
    rows = list(
        db.scalars(
            select(Notification).where(due).order_by(Notification.next_attempt_at)
            .limit(limit).with_for_update(skip_locked=True)
        )
    )
    for n in rows:
        n.status = NotificationStatus.sending
        n.lease_until = now + LEASE
        n.attempts += 1
    db.commit()
    return [n.id for n in rows]


def deliver(db: Session, notification_id: uuid.UUID, email_sender, sms_sender, now: datetime) -> str | None:
    n = db.get(Notification, notification_id)
    if n is None or n.status != NotificationStatus.sending:
        return None

    if n.attempts > MAX_ATTEMPTS:       # claimed again and again by workers that died
        n.status = NotificationStatus.failed
        n.last_error = "Gave up after repeated worker crashes"
        outcome = "failed"
    else:
        try:
            if n.channel == Channel.email:
                ref = email_sender.send(to=n.to_address, subject=n.subject or "", text=n.body_text, html=n.body_html)
            else:
                ref = sms_sender.send(to=n.to_address, message=n.body_text)
        except PermanentSendError as exc:
            n.status = NotificationStatus.failed
            n.last_error = str(exc)[:500]
            outcome = "failed"
        except Exception as exc:
            log.warning("Notification %s, attempt %s failed: %s", n.id, n.attempts, exc)
            n.last_error = str(exc)[:500]
            if n.attempts >= MAX_ATTEMPTS:
                n.status = NotificationStatus.failed
                outcome = "failed"
            else:
                n.status = NotificationStatus.pending
                n.next_attempt_at = now + BACKOFF[min(n.attempts - 1, len(BACKOFF) - 1)]
                outcome = "retry"
        else:
            n.status = NotificationStatus.sent
            n.sent_at = now
            n.provider_ref = (ref or None) and str(ref)[:100]
            n.last_error = None
            outcome = "sent"

    n.lease_until = None
    if n.sensitive and n.status in (NotificationStatus.sent, NotificationStatus.failed):
        n.body_text = "[redacted]"          # a working reset link must not sit in the outbox
        n.body_html = None
    db.commit()
    return outcome


def process_due(
    db: Session, email_sender, sms_sender, *, now: datetime | None = None,
    batch_size: int = 20, max_batches: int = 10,
) -> dict:
    """Worker job: send everything that's due. Commits."""
    now = now or _now()
    result = {"sent": 0, "retry": 0, "failed": 0}
    for _ in range(max_batches):
        ids = claim_due(db, now, batch_size)
        if not ids:
            break
        for notification_id in ids:
            outcome = deliver(db, notification_id, email_sender, sms_sender, now)
            if outcome:
                result[outcome] += 1
    return result


def purge_old(db: Session, days: int = 90) -> int:
    """Worker job: delete delivered or failed messages after `days`. They contain personal data."""
    cutoff = _now() - timedelta(days=days)
    res = db.execute(
        delete(Notification).where(
            Notification.status.in_([NotificationStatus.sent, NotificationStatus.failed]),
            Notification.created_at < cutoff,
        )
    )
    db.commit()
    return res.rowcount or 0