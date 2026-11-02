import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DistanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    km: Decimal
    fee: Decimal
    capacity: int
    min_age: int


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    event_date: date
    location: str
    registration_opens: date
    registration_closes: date
    distances: list[DistanceOut]