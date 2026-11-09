import uuid
from datetime import date, datetime, time
from decimal import Decimal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.events.models import EventStatus
from app.modules.registrations.models import RegistrationStatus
from app.utils.phone import normalize_phone

# ----------------------------------------------------------------- input
class DistanceIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=30)
    km: Decimal = Field(gt=0, le=500, max_digits=5, decimal_places=2)
    fee: int = Field(ge=0, le=1_000_000, description="Whole Kenya shillings. 0 means free.")
    capacity: int = Field(ge=1, le=100_000)
    min_age: int = Field(default=12, ge=0, le=100)
    start_time: time | None = None
    cutoff_minutes: int | None = Field(default=None, ge=15, le=1440)


class DistanceUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=30)
    km: Decimal | None = Field(default=None, gt=0, le=500, max_digits=5, decimal_places=2)
    fee: int | None = Field(default=None, ge=0, le=1_000_000)
    capacity: int | None = Field(default=None, ge=1, le=100_000)
    min_age: int | None = Field(default=None, ge=0, le=100)
    start_time: time | None = None
    cutoff_minutes: int | None = Field(default=None, ge=15, le=1440)


class EventContent(BaseModel):
    """The descriptive fields of an event. All optional, and blank means "none"."""
    description: str | None = Field(default=None, max_length=5000)
    venue_details: str | None = Field(default=None, max_length=1000)
    map_url: str | None = Field(default=None, max_length=500)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=20)

    @field_validator("description", "venue_details", "map_url", "contact_email", "contact_phone", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("map_url")
    @classmethod
    def map_url_is_https(cls, v: str | None) -> str | None:
        if v is None:
            return None
        parsed = urlparse(v)
        if parsed.scheme != "https" or not parsed.netloc or " " in v:
            raise ValueError("Enter a full link starting with https://")
        return v

    @field_validator("contact_phone")
    @classmethod
    def phone_is_valid(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v else None


class EventIn(EventContent):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=3, max_length=150)
    event_date: date
    location: str = Field(min_length=2, max_length=150)
    registration_opens: date
    registration_closes: date
    refunds_until: date | None = None
    distances: list[DistanceIn] = Field(default_factory=list, max_length=10)

    @field_validator("distances")
    @classmethod
    def unique_names(cls, v: list[DistanceIn]) -> list[DistanceIn]:
        names = [d.name.lower() for d in v]
        if len(names) != len(set(names)):
            raise ValueError("Distance names must be unique within an event")
        return v


class EventUpdate(EventContent):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=3, max_length=150)
    event_date: date | None = None
    location: str | None = Field(default=None, min_length=2, max_length=150)
    registration_opens: date | None = None
    registration_closes: date | None = None
    refunds_until: date | None = None


# ----------------------------------------------------------------- output
class DistanceAdminOut(BaseModel):
    id: uuid.UUID
    name: str
    km: Decimal
    fee: Decimal
    capacity: int
    min_age: int
    confirmed: int
    held: int          # unpaid, but still holding a spot
    spots_left: int
    start_time: time | None
    cutoff_minutes: int | None


class EventAdminOut(BaseModel):
    id: uuid.UUID
    name: str
    event_date: date
    location: str
    registration_opens: date
    registration_closes: date
    refunds_until: date | None
    status: EventStatus
    cancelled_at: datetime | None
    cancellation_reason: str | None
    confirmed: int
    held: int
    distances: list[DistanceAdminOut]
    description: str | None
    venue_details: str | None
    map_url: str | None
    contact_email: str | None
    contact_phone: str | None
    banner_url: str | None


class EventSummaryOut(BaseModel):
    id: uuid.UUID
    name: str
    event_date: date
    location: str
    status: EventStatus
    capacity: int
    confirmed: int
    held: int


class ParticipantOut(BaseModel):
    registration_id: uuid.UUID
    bib_number: int
    status: RegistrationStatus
    distance_name: str
    full_name: str
    email: str
    phone: str | None
    gender: str | None
    age_category: str | None
    club: str | None
    tshirt_size: str | None
    registered_at: datetime


class ParticipantPage(BaseModel):
    items: list[ParticipantOut]
    total: int


class CancelEventIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500, description="Shown to everyone who registered.")


class CancelPreviewOut(BaseModel):
    registrations: int
    paid_registrations: int
    refund_total: Decimal
