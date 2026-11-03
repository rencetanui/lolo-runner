import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .models import RegistrationStatus


class RegistrationIn(BaseModel):
    distance_id: uuid.UUID
    waiver_version: str = Field(max_length=30)
    guardian_consent: bool = False
    estimated_finish_minutes: int | None = Field(default=None, ge=15, le=600)


class EventBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    event_date: date
    location: str


class DistanceBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    km: Decimal


class RegistrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: RegistrationStatus
    bib_number: int
    fee_amount: Decimal
    estimated_finish_minutes: int | None
    expires_at: datetime | None
    created_at: datetime
    event: EventBrief
    distance: DistanceBrief


class AvailabilityOut(BaseModel):
    distance_id: uuid.UUID
    capacity: int
    spots_left: int


class WaiverOut(BaseModel):
    version: str
    text: str