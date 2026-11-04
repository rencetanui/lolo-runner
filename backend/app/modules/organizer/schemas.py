import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.events.models import EventStatus
from app.modules.registrations.models import RegistrationStatus


# ----------------------------------------------------------------- input
class DistanceIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=30)
    km: Decimal = Field(gt=0, le=500, max_digits=5, decimal_places=2)
    fee: int = Field(ge=0, le=1_000_000, description="Whole Kenya shillings. 0 means free.")
    capacity: int = Field(ge=1, le=100_000)
    min_age: int = Field(default=12, ge=0, le=100)


class DistanceUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=30)
    km: Decimal | None = Field(default=None, gt=0, le=500, max_digits=5, decimal_places=2)
    fee: int | None = Field(default=None, ge=0, le=1_000_000)
    capacity: int | None = Field(default=None, ge=1, le=100_000)
    min_age: int | None = Field(default=None, ge=0, le=100)


class EventIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=3, max_length=150)
    event_date: date
    location: str = Field(min_length=2, max_length=150)
    registration_opens: date
    registration_closes: date
    distances: list[DistanceIn] = Field(default_factory=list, max_length=10)

    @field_validator("distances")
    @classmethod
    def unique_names(cls, v: list[DistanceIn]) -> list[DistanceIn]:
        names = [d.name.lower() for d in v]
        if len(names) != len(set(names)):
            raise ValueError("Distance names must be unique within an event")
        return v


class EventUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=3, max_length=150)
    event_date: date | None = None
    location: str | None = Field(default=None, min_length=2, max_length=150)
    registration_opens: date | None = None
    registration_closes: date | None = None


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


class EventAdminOut(BaseModel):
    id: uuid.UUID
    name: str
    event_date: date
    location: str
    registration_opens: date
    registration_closes: date
    status: EventStatus
    confirmed: int
    held: int
    distances: list[DistanceAdminOut]


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
    # Deliberately NOT here: medical notes and emergency contact details.


class ParticipantPage(BaseModel):
    items: list[ParticipantOut]
    total: int