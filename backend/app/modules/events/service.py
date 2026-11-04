import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Event, EventStatus


def list_events(db: Session, upcoming_only: bool, limit: int, offset: int) -> list[Event]:
    stmt = select(Event).options(selectinload(Event.distances)).order_by(Event.event_date).where(Event.status == EventStatus.published)
    if upcoming_only:
        stmt = stmt.where(Event.event_date >= date.today())
    return list(db.scalars(stmt.limit(limit).offset(offset)))


def get_event(db: Session, event_id: uuid.UUID) -> Event | None:
    stmt = (
        select(Event)
        .options(selectinload(Event.distances))
        .where(Event.id == event_id, Event.status == EventStatus.published)
    )
    return db.scalars(stmt).first()