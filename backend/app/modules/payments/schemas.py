import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.phone import normalize_phone

from .models import PaymentStatus


class PaymentIn(BaseModel):
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        return normalize_phone(v)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    registration_id: uuid.UUID
    status: PaymentStatus
    amount: Decimal
    phone: str
    result_desc: str | None
    created_at: datetime
    completed_at: datetime | None