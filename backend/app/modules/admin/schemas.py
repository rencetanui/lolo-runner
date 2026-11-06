import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.payments.models import PaymentStatus
from app.modules.registrations.models import RegistrationStatus


class PersonOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str


class EventRef(BaseModel):
    id: uuid.UUID
    name: str
    event_date: date


class AuditOut(BaseModel):
    created_at: datetime
    action: str
    actor_name: str | None
    detail: dict | None


class AdminPaymentOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    completed_at: datetime | None
    status: PaymentStatus
    amount: Decimal
    phone: str
    mpesa_receipt: str | None
    result_code: int | None
    result_desc: str | None
    needs_refund: bool
    admin_note: str | None
    user: PersonOut
    event: EventRef
    distance_name: str
    bib_number: int
    registration_id: uuid.UUID
    registration_status: RegistrationStatus


class AdminPaymentDetail(AdminPaymentOut):
    raw_callback: dict | None
    audit: list[AuditOut]


class AdminPaymentPage(BaseModel):
    items: list[AdminPaymentOut]
    total: int


class AdminSummary(BaseModel):
    needs_review: int
    needs_refund: int
    stuck_pending: int      # still waiting on M-Pesa after 10 minutes
    failed_24h: int


class ResolveIn(BaseModel):
    action: Literal["confirm", "dismiss"]
    note: str = Field(min_length=10, max_length=500, description="Why. Kept in the audit log.")
    mpesa_receipt: str | None = Field(default=None, max_length=30)

    @field_validator("mpesa_receipt")
    @classmethod
    def blank_to_none(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None