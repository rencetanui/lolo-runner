import csv
import io
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.storage import delete_media, save_media
from app.modules.audit.service import log_action
from app.modules.auth.models import Role, User
from app.modules.events.models import Distance, Event, EventStatus
from app.modules.notifications.service import (
    notify_admins_refunds_queued,
    notify_event_cancelled,
    notify_event_changed,
    notify_start_time_changed,
)
from app.modules.refunds.service import refund_for_event_cancellation
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.registrations.service import expire_stale, holding_spot
from app.modules.runners.models import RunnerProfile
from app.utils.age import age_category, age_on
from app.utils.dates import today_ke
from app.utils.images import ImageError, process_banner

from .schemas import (
    CancelPreviewOut,
    DistanceAdminOut,
    DistanceIn,
    DistanceUpdate,
    EventAdminOut,
    EventIn,
    EventSummaryOut,
    EventUpdate,
    ParticipantOut,
    ParticipantPage,
)

MAX_DISTANCES = 10
# Optional fields an organizer may set back to empty (everything else ignores null).
CLEARABLE = ("refunds_until", "description", "venue_details", "map_url", "contact_email", "contact_phone")


class OrganizerError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code


# ------------------------------------------------------------ helpers
def _get_manageable(db: Session, user: User, event_id: uuid.UUID, *, lock: bool = False) -> Event:
    """The event, if this user may manage it. Others get a 404 so event IDs don't leak."""
    stmt = select(Event).where(Event.id == event_id)
    if lock:
        stmt = stmt.with_for_update()
    event = db.scalars(stmt).first()
    if not event or (user.role != Role.admin and event.created_by != user.id):
        raise OrganizerError("event_not_found", "Event not found", 404)
    if lock and event.status == EventStatus.cancelled:
        raise OrganizerError("event_cancelled", "This event has been cancelled and can't be changed.", 409)
    return event


def _find_distance(event: Event, distance_id: uuid.UUID) -> Distance:
    distance = next((d for d in event.distances if d.id == distance_id), None)
    if not distance:
        raise OrganizerError("distance_not_found", "Distance not found", 404)
    return distance


def _check_dates(opens, closes, event_date) -> None:
    if not (opens <= closes <= event_date):
        raise OrganizerError(
            "invalid_dates",
            "Registration must open before it closes, and close on or before the event date.",
            422,
        )


def _check_refund_date(refunds_until, event_date) -> None:
    if refunds_until is not None and refunds_until > event_date:
        raise OrganizerError("invalid_refund_date", "Refunds must end on or before the event date.", 422)


def _check_not_past(event_date) -> None:
    if event_date < today_ke():
        raise OrganizerError("event_in_past", "The event date can't be in the past.", 422)


def _check_name_free(event: Event, name: str, ignore_id: uuid.UUID | None = None) -> None:
    if any(d.name.lower() == name.lower() and d.id != ignore_id for d in event.distances):
        raise OrganizerError("duplicate_distance", f'This event already has a "{name}" distance.')


def _remove_banner_files(key: str) -> None:
    delete_media(f"events/{key}.jpg")
    delete_media(f"events/{key}-og.jpg")


def _taken(db: Session, event_id: uuid.UUID) -> dict:
    """distance_id -> [confirmed, held] for confirmed and still-live unpaid registrations."""
    rows = db.execute(
        select(Registration.distance_id, Registration.status, func.count())
        .where(Registration.event_id == event_id, holding_spot())
        .group_by(Registration.distance_id, Registration.status)
    ).all()
    taken: dict = defaultdict(lambda: [0, 0])
    for distance_id, status, n in rows:
        taken[distance_id][0 if status == RegistrationStatus.confirmed else 1] += n
    return taken


def to_admin_out(db: Session, event: Event) -> EventAdminOut:
    taken = _taken(db, event.id)
    distances = []
    for d in event.distances:
        confirmed, held = taken.get(d.id, (0, 0))
        distances.append(
            DistanceAdminOut(
                id=d.id, name=d.name, km=d.km, fee=d.fee, capacity=d.capacity, min_age=d.min_age,
                start_time=d.start_time, cutoff_minutes=d.cutoff_minutes,
                confirmed=confirmed, held=held,
                spots_left=max(d.capacity - confirmed - held, 0),
            )
        )
    return EventAdminOut(
        id=event.id, name=event.name, event_date=event.event_date, location=event.location,
        registration_opens=event.registration_opens, registration_closes=event.registration_closes,
        refunds_until=event.refunds_until, status=event.status,
        cancelled_at=event.cancelled_at, cancellation_reason=event.cancellation_reason,
        description=event.description, venue_details=event.venue_details, map_url=event.map_url,
        contact_email=event.contact_email, contact_phone=event.contact_phone, banner_url=event.banner_url,
        distances=distances,
        confirmed=sum(d.confirmed for d in distances), held=sum(d.held for d in distances),
    )


def _finish(db: Session, event: Event) -> EventAdminOut:
    db.commit()
    db.refresh(event)      # reload so distances come back in the right order
    return to_admin_out(db, event)


# ------------------------------------------------------------ events
def list_events(db: Session, user: User) -> list[EventSummaryOut]:
    stmt = select(Event).order_by(Event.event_date.desc())
    if user.role != Role.admin:
        stmt = stmt.where(Event.created_by == user.id)
    events = list(db.scalars(stmt))
    if not events:
        return []

    ids = [e.id for e in events]
    capacity = dict(
        db.execute(
            select(Distance.event_id, func.sum(Distance.capacity))
            .where(Distance.event_id.in_(ids))
            .group_by(Distance.event_id)
        ).all()
    )
    counts: dict = defaultdict(lambda: [0, 0])
    for event_id, status, n in db.execute(
        select(Registration.event_id, Registration.status, func.count())
        .where(Registration.event_id.in_(ids), holding_spot())
        .group_by(Registration.event_id, Registration.status)
    ).all():
        counts[event_id][0 if status == RegistrationStatus.confirmed else 1] += n

    return [
        EventSummaryOut(
            id=e.id, name=e.name, event_date=e.event_date, location=e.location, status=e.status,
            capacity=int(capacity.get(e.id) or 0),
            confirmed=counts[e.id][0], held=counts[e.id][1],
        )
        for e in events
    ]


def get_event(db: Session, user: User, event_id: uuid.UUID) -> EventAdminOut:
    event = _get_manageable(db, user, event_id)
    expire_stale(db, event_id=event.id)
    db.commit()
    return to_admin_out(db, event)


def create_event(db: Session, user: User, data: EventIn) -> EventAdminOut:
    _check_dates(data.registration_opens, data.registration_closes, data.event_date)
    _check_not_past(data.event_date)
    _check_refund_date(data.refunds_until, data.event_date)
    event = Event(
        name=data.name,
        event_date=data.event_date,
        location=data.location,
        registration_opens=data.registration_opens,
        registration_closes=data.registration_closes,
        refunds_until=data.refunds_until,
        description=data.description,
        venue_details=data.venue_details,
        map_url=data.map_url,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        status=EventStatus.draft,
        created_by=user.id,
        distances=[Distance(**d.model_dump()) for d in data.distances],
    )
    db.add(event)
    return _finish(db, event)


def update_event(db: Session, user: User, event_id: uuid.UUID, data: EventUpdate) -> EventAdminOut:
    event = _get_manageable(db, user, event_id, lock=True)
    given = data.model_dump(exclude_unset=True)
    changes = {k: v for k, v in given.items() if k not in CLEARABLE and v is not None}
    cleared = {k: given[k] for k in CLEARABLE if k in given}       # these may be set to empty
    merged = {k: changes.get(k, getattr(event, k)) for k in ("event_date", "registration_opens", "registration_closes")}
    _check_dates(merged["registration_opens"], merged["registration_closes"], merged["event_date"])
    if "event_date" in changes:
        _check_not_past(changes["event_date"])
    refunds_until = cleared["refunds_until"] if "refunds_until" in cleared else event.refunds_until
    _check_refund_date(refunds_until, merged["event_date"])

    # Only a new date or location is worth an email and an SMS. A renamed event is not.
    # This compares the values that will really be saved (`changes`), never a raw null from the request.
    notable = {
        key: (getattr(event, key), changes[key])
        for key in ("event_date", "location")
        if key in changes and changes[key] != getattr(event, key)
    }
    for key, value in {**changes, **cleared}.items():
        setattr(event, key, value)
    if notable and event.status == EventStatus.published:
        expire_stale(db, event_id=event.id)      # don't message people whose unpaid hold has lapsed
        notify_event_changed(db, event, notable)
    return _finish(db, event)


def publish_event(db: Session, user: User, event_id: uuid.UUID) -> EventAdminOut:
    event = _get_manageable(db, user, event_id, lock=True)
    if event.status == EventStatus.published:
        return to_admin_out(db, event)
    if not event.distances:
        raise OrganizerError("no_distances", "Add at least one distance before publishing.", 422)
    _check_not_past(event.event_date)
    if event.registration_closes < today_ke():
        raise OrganizerError("registration_already_closed", "Registration has already closed. Update the dates first.", 422)
    event.status = EventStatus.published
    return _finish(db, event)


def unpublish_event(db: Session, user: User, event_id: uuid.UUID) -> EventAdminOut:
    event = _get_manageable(db, user, event_id, lock=True)
    if event.status == EventStatus.draft:
        return to_admin_out(db, event)
    expire_stale(db, event_id=event.id)
    active = db.scalar(
        select(func.count()).select_from(Registration).where(Registration.event_id == event.id, holding_spot())
    )
    if active:
        raise OrganizerError(
            "has_registrations",
            f"{active} runner(s) are registered or holding a spot, so this event can't be unpublished.",
        )
    event.status = EventStatus.draft
    return _finish(db, event)


def delete_event(db: Session, user: User, event_id: uuid.UUID) -> None:
    event = _get_manageable(db, user, event_id, lock=True)
    used = db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == event.id))
    if used:
        raise OrganizerError("event_has_registrations", "Events that have had registrations can't be deleted.")
    banner = event.banner_file
    db.delete(event)
    db.commit()
    if banner:
        _remove_banner_files(banner)


def cancel_preview(db: Session, user: User, event_id: uuid.UUID) -> CancelPreviewOut:
    event = _get_manageable(db, user, event_id)
    expire_stale(db, event_id=event.id)
    db.commit()
    regs = list(
        db.scalars(select(Registration).where(Registration.event_id == event.id, Registration.status != RegistrationStatus.cancelled))
    )
    paid = [r for r in regs if r.status == RegistrationStatus.confirmed and r.fee_amount > 0]
    return CancelPreviewOut(
        registrations=len(regs),
        paid_registrations=len(paid),
        refund_total=sum((r.fee_amount for r in paid), Decimal(0)),
    )


def cancel_event(db: Session, user: User, event_id: uuid.UUID, reason: str) -> EventAdminOut:
    """Cancel the event, every registration, and queue a full refund for each one that paid."""
    event = _get_manageable(db, user, event_id, lock=True)
    if event.status != EventStatus.published:
        raise OrganizerError("not_published", "Only published events can be cancelled. Delete a draft instead.", 409)
    if event.event_date < today_ke():
        raise OrganizerError("event_in_past", "This event has already taken place.", 422)

    expire_stale(db, event_id=event.id)
    now = datetime.now(timezone.utc)
    regs = list(
        db.scalars(select(Registration).where(Registration.event_id == event.id, Registration.status != RegistrationStatus.cancelled))
    )
    event.status = EventStatus.cancelled
    event.cancelled_at = now
    event.cancellation_reason = reason.strip()

    refunds = []
    for reg in regs:
        was_paid = reg.status == RegistrationStatus.confirmed and reg.fee_amount > 0
        reg.status = RegistrationStatus.cancelled
        reg.cancelled_at = now
        refund = refund_for_event_cancellation(db, reg, was_paid=was_paid, actor=user)
        if refund:
            refunds.append(refund)

    refunds_by_reg = {r.registration_id: r for r in refunds}
    log_action(
        db, user, "event.cancelled", "event", event.id,
        reason=event.cancellation_reason, registrations=len(regs), refunds=len(refunds),
    )
    notify_event_cancelled(db, event, regs, refunds_by_reg)
    if refunds:
        notify_admins_refunds_queued(db, event, len(refunds), sum((r.amount for r in refunds), Decimal(0)))
    return _finish(db, event)


def set_banner(db: Session, user: User, event_id: uuid.UUID, data: bytes) -> EventAdminOut:
    event = _get_manageable(db, user, event_id, lock=True)
    try:
        banner, share = process_banner(data)
    except ImageError as exc:
        raise OrganizerError("invalid_image", str(exc), 422)
    key = uuid.uuid4().hex
    save_media(f"events/{key}.jpg", banner)
    save_media(f"events/{key}-og.jpg", share)
    old = event.banner_file
    event.banner_file = key
    try:
        result = _finish(db, event)
    except Exception:
        _remove_banner_files(key)
        raise
    if old:
        _remove_banner_files(old)
    return result


def delete_banner(db: Session, user: User, event_id: uuid.UUID) -> EventAdminOut:
    event = _get_manageable(db, user, event_id, lock=True)
    old = event.banner_file
    event.banner_file = None
    result = _finish(db, event)
    if old:
        _remove_banner_files(old)
    return result


# ------------------------------------------------------------ distances
def add_distance(db: Session, user: User, event_id: uuid.UUID, data: DistanceIn) -> EventAdminOut:
    event = _get_manageable(db, user, event_id, lock=True)
    if len(event.distances) >= MAX_DISTANCES:
        raise OrganizerError("too_many_distances", f"An event can have at most {MAX_DISTANCES} distances.", 422)
    _check_name_free(event, data.name)
    event.distances.append(Distance(**data.model_dump()))
    return _finish(db, event)


def update_distance(
    db: Session, user: User, event_id: uuid.UUID, distance_id: uuid.UUID, data: DistanceUpdate
) -> EventAdminOut:
    event = _get_manageable(db, user, event_id, lock=True)
    distance = _find_distance(event, distance_id)
    given = data.model_dump(exclude_unset=True)
    clearable = ("start_time", "cutoff_minutes")
    changes = {k: v for k, v in given.items() if v is not None and k not in clearable}
    cleared = {k: given[k] for k in clearable if k in given}
    if "name" in changes:
        _check_name_free(event, changes["name"], ignore_id=distance.id)

    expire_stale(db, event_id=event.id)
    confirmed, held = _taken(db, event.id).get(distance.id, (0, 0))
    taken = confirmed + held
    if taken:
        locked = [k for k in ("name", "km", "min_age") if k in changes and getattr(distance, k) != changes[k]]
        if locked:
            raise OrganizerError(
                "distance_locked",
                "Name, distance and minimum age can't change once runners have registered.",
            )
        if "capacity" in changes and changes["capacity"] < taken:
            raise OrganizerError(
                "capacity_below_registrations",
                f"{taken} runner(s) are already registered or holding a spot, so capacity can't go below {taken}.",
            )
    old_start = distance.start_time
    for key, value in {**changes, **cleared}.items():
        setattr(distance, key, value)
    if (
        "start_time" in cleared and cleared["start_time"] != old_start
        and event.status == EventStatus.published and taken
    ):
        notify_start_time_changed(db, event, distance, old_start, cleared["start_time"])
    return _finish(db, event)


def delete_distance(db: Session, user: User, event_id: uuid.UUID, distance_id: uuid.UUID) -> EventAdminOut:
    event = _get_manageable(db, user, event_id, lock=True)
    distance = _find_distance(event, distance_id)
    used = db.scalar(select(func.count()).select_from(Registration).where(Registration.distance_id == distance.id))
    if used:
        raise OrganizerError("distance_has_registrations", "This distance has registrations, so it can't be deleted.")
    if event.status == EventStatus.published and len(event.distances) == 1:
        raise OrganizerError("last_distance", "A published event needs at least one distance. Unpublish it first.")
    event.distances.remove(distance)
    return _finish(db, event)


# ------------------------------------------------------------ participants
def _participant_stmt(event: Event, include_cancelled: bool):
    stmt = (
        select(Registration, User, RunnerProfile)
        .join(User, User.id == Registration.user_id)
        .outerjoin(RunnerProfile, RunnerProfile.user_id == Registration.user_id)
        .where(Registration.event_id == event.id)
        .order_by(Registration.bib_number)
    )
    if not include_cancelled:
        stmt = stmt.where(Registration.status != RegistrationStatus.cancelled)
    return stmt


def _to_participant(event: Event, reg: Registration, user: User, profile: RunnerProfile | None) -> ParticipantOut:
    category = None
    if profile:
        category = age_category(age_on(profile.date_of_birth, event.event_date), profile.gender.value)
    return ParticipantOut(
        registration_id=reg.id,
        bib_number=reg.bib_number,
        status=reg.status,
        distance_name=reg.distance.name,
        full_name=user.full_name,
        email=user.email,
        phone=profile.phone if profile else None,
        gender=profile.gender.value if profile else None,
        age_category=category,
        club=profile.club if profile else None,
        tshirt_size=profile.tshirt_size.value if profile else None,
        registered_at=reg.created_at,
    )


def list_participants(
    db: Session, user: User, event_id: uuid.UUID, *, include_cancelled: bool, limit: int, offset: int
) -> ParticipantPage:
    event = _get_manageable(db, user, event_id)
    expire_stale(db, event_id=event.id)
    db.commit()
    rows = db.execute(_participant_stmt(event, include_cancelled).limit(limit).offset(offset)).all()
    count_stmt = select(func.count()).select_from(Registration).where(Registration.event_id == event.id)
    if not include_cancelled:
        count_stmt = count_stmt.where(Registration.status != RegistrationStatus.cancelled)
    return ParticipantPage(
        items=[_to_participant(event, reg, u, profile) for reg, u, profile in rows],
        total=db.scalar(count_stmt) or 0,
    )


def _csv_safe(value: str | None) -> str:
    """Stop spreadsheet apps from running user-entered text as a formula."""
    s = value or ""
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def participants_csv(db: Session, user: User, event_id: uuid.UUID) -> tuple[str, str]:
    event = _get_manageable(db, user, event_id)
    expire_stale(db, event_id=event.id)
    db.commit()
    rows = db.execute(_participant_stmt(event, False)).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["Bib", "Name", "Email", "Phone", "Distance", "Status", "Gender", "Age category",
         "Club", "T-shirt", "Registered at (UTC)"]
    )
    for reg, u, profile in rows:
        p = _to_participant(event, reg, u, profile)
        writer.writerow([
            p.bib_number, _csv_safe(p.full_name), _csv_safe(p.email), p.phone or "",
            p.distance_name, p.status.value, p.gender or "", p.age_category or "",
            _csv_safe(p.club), p.tshirt_size or "", p.registered_at.strftime("%Y-%m-%d %H:%M"),
        ])
    slug = re.sub(r"[^a-z0-9]+", "-", event.name.lower()).strip("-") or "event"
    return "\ufeff" + buf.getvalue(), f"{slug}-participants.csv"   # BOM: Excel reads UTF-8 correctly