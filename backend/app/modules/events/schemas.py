import uuid
from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from .models import EventStatus


class DistanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    km: Decimal
    fee: Decimal
    capacity: int
    min_age: int
    start_time: time | None
    cutoff_minutes: int | None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    event_date: date
    location: str
    registration_opens: date
    registration_closes: date
    distances: list[DistanceOut]
    status: EventStatus
    refunds_until: date | None
    cancellation_reason: str | None
    description: str | None
    venue_details: str | None
    map_url: str | None
    contact_email: str | None
    contact_phone: str | None
    banner_url: str | None