import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.models import User
from app.modules.events.models import Event, EventStatus
from app.modules.runners.models import RunnerProfile
from app.modules.notifications.service import notify_registration_confirmed, notify_registration_cancelled
from app.utils.age import age_on
from app.utils.dates import today_ke

from .models import Registration, RegistrationStatus
from .schemas import AvailabilityOut, RegistrationIn
from .waiver import WAIVER_VERSION


class RegistrationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def holding_spot():
    """Confirmed registrations, plus unpaid ones whose hold hasn't expired."""
    return or_(
        Registration.status == RegistrationStatus.confirmed,
        and_(
            Registration.status == RegistrationStatus.pending_payment,
            Registration.expires_at > _now(),
        ),
    )


def expire_stale(db: Session, *, event_id: uuid.UUID | None = None,
                 user_id: uuid.UUID | None = None) -> None:
    stmt = (
        update(Registration)
        .where(
            Registration.status == RegistrationStatus.pending_payment,
            Registration.expires_at < _now(),
        )
        .values(status=RegistrationStatus.cancelled, cancelled_at=_now())
    )
    if event_id:
        stmt = stmt.where(Registration.event_id == event_id)
    if user_id:
        stmt = stmt.where(Registration.user_id == user_id)
    db.execute(stmt)


def availability(db: Session, event_id: uuid.UUID) -> list[AvailabilityOut]:
    event = db.get(Event, event_id)
    if not event or event.status != EventStatus.published:
        raise RegistrationError("event_not_found", "Event not found", 404)
    rows = db.execute(
        select(Registration.distance_id, func.count())
        .where(Registration.event_id == event_id, holding_spot())
        .group_by(Registration.distance_id)
    ).all()
    taken = dict(rows)
    return [
        AvailabilityOut(
            distance_id=d.id,
            capacity=d.capacity,
            spots_left=max(d.capacity - taken.get(d.id, 0), 0),
        )
        for d in event.distances
    ]


def register(db: Session, user: User, event_id: uuid.UUID, data: RegistrationIn) -> Registration:
    # Lock the event row until commit: registrations for one event are processed
    # one at a time, so capacity and bib numbers can't be raced.
    event = db.scalars(select(Event).where(Event.id == event_id).with_for_update()).first()
    if not event or event.status != EventStatus.published:
        raise RegistrationError("event_not_found", "Event not found", 404)

    profile = db.scalars(
        select(RunnerProfile).where(RunnerProfile.user_id == user.id)
    ).first()
    if not profile:
        raise RegistrationError("profile_required", "Complete your runner profile before registering")

    today = today_ke()
    if today < event.registration_opens:
        raise RegistrationError("registration_not_open", "Registration for this event hasn't opened yet")
    if today > event.registration_closes:
        raise RegistrationError("registration_closed", "Registration for this event is closed")

    distance = next((d for d in event.distances if d.id == data.distance_id), None)
    if not distance:
        raise RegistrationError("distance_not_found", "That distance isn't part of this event", 404)

    if data.waiver_version != WAIVER_VERSION:
        raise RegistrationError(
            "waiver_outdated", "The waiver has been updated. Please review and accept it again.", 422
        )

    age = age_on(profile.date_of_birth, event.event_date)
    if age < distance.min_age:
        raise RegistrationError(
            "too_young", f"The minimum age for the {distance.name} is {distance.min_age}."
        )
    if age < 18 and not data.guardian_consent:
        raise RegistrationError(
            "guardian_consent_required",
            "A parent or guardian must consent for runners under 18.",
            422,
        )

    expire_stale(db, event_id=event.id)

    already = db.scalars(
        select(Registration).where(
            Registration.user_id == user.id,
            Registration.event_id == event.id,
            Registration.status != RegistrationStatus.cancelled,
        )
    ).first()
    if already:
        raise RegistrationError(
            "already_registered", "You're already registered for this event. Cancel it first to change distance."
        )

    taken = db.scalar(
        select(func.count())
        .select_from(Registration)
        .where(Registration.distance_id == distance.id, holding_spot())
    )
    if taken >= distance.capacity:
        raise RegistrationError("sold_out", f"The {distance.name} is sold out.")

    last_bib = db.scalar(
        select(func.max(Registration.bib_number)).where(Registration.event_id == event.id)
    )
    free = distance.fee == 0
    registration = Registration(
        user_id=user.id,
        event_id=event.id,
        distance_id=distance.id,
        bib_number=(last_bib or 0) + 1,
        status=RegistrationStatus.confirmed if free else RegistrationStatus.pending_payment,
        fee_amount=distance.fee,
        estimated_finish_minutes=data.estimated_finish_minutes,
        waiver_version=data.waiver_version,
        waiver_accepted_at=_now(),
        guardian_consent=data.guardian_consent,
        expires_at=None if free else _now() + timedelta(minutes=settings.registration_hold_minutes),
    )
    db.add(registration)
    try:
        if free:
            db.flush()  # so we can send the confirmation email before commit
            notify_registration_confirmed(db, registration)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise RegistrationError("conflict", "That didn't go through. Please try again.")
    db.refresh(registration)
    return registration


def _get_owned(db: Session, user: User, registration_id: uuid.UUID) -> Registration:
    reg = db.get(Registration, registration_id)
    if not reg or reg.user_id != user.id:
        raise RegistrationError("registration_not_found", "Registration not found", 404)
    return reg


def get_mine(db: Session, user: User, registration_id: uuid.UUID) -> Registration:
    expire_stale(db, user_id=user.id)
    db.commit()
    return _get_owned(db, user, registration_id)


def list_mine(db: Session, user: User) -> list[Registration]:
    expire_stale(db, user_id=user.id)
    db.commit()
    return list(
        db.scalars(
            select(Registration)
            .where(Registration.user_id == user.id, Registration.status != RegistrationStatus.cancelled)
            .order_by(Registration.created_at.desc())
        ).unique()
    )


def cancel(db: Session, user: User, registration_id: uuid.UUID) -> Registration:
    reg = _get_owned(db, user, registration_id)
    if reg.status == RegistrationStatus.cancelled:
        return reg  # idempotent
    if reg.event.event_date <= today_ke():
        raise RegistrationError("event_started", "This event has already started, so it can't be cancelled.")
    reg.status = RegistrationStatus.cancelled
    reg.cancelled_at = _now()
    notify_registration_cancelled(db, reg)
    db.commit()
    db.refresh(reg)
    return reg