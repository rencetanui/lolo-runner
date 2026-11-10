import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.payments.models import PaymentStatus
from app.modules.refunds.models import RefundReason, RefundStatus
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


class RefundBrief(BaseModel):
    id: uuid.UUID
    status: RefundStatus
    reason: RefundReason
    amount: Decimal
    created_at: datetime
    mpesa_reference: str | None


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
    refunds: list[RefundBrief]


class AdminPaymentPage(BaseModel):
    items: list[AdminPaymentOut]
    total: int


class AdminSummary(BaseModel):
    needs_review: int
    needs_refund: int
    stuck_pending: int      # still waiting on M-Pesa after 10 minutes
    failed_24h: int
    refunds_requested: int  # refunds waiting for you to send the money
    support_open: int

class ResolveIn(BaseModel):
    action: Literal["confirm", "dismiss"]
    note: str = Field(min_length=10, max_length=500, description="Why. Kept in the audit log.")
    mpesa_receipt: str | None = Field(default=None, max_length=30)

    @field_validator("mpesa_receipt")
    @classmethod
    def blank_to_none(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None


class AdminRefundOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    decided_at: datetime | None
    status: RefundStatus
    reason: RefundReason
    amount: Decimal
    phone: str
    mpesa_reference: str | None
    admin_note: str | None
    user: PersonOut
    event: EventRef
    distance_name: str
    bib_number: int
    registration_id: uuid.UUID
    payment_id: uuid.UUID
    payment_receipt: str | None
    decided_by_name: str | None


class AdminRefundDetail(AdminRefundOut):
    audit: list[AuditOut]


class AdminRefundPage(BaseModel):
    items: list[AdminRefundOut]
    total: int


class MarkPaidIn(BaseModel):
    mpesa_reference: str = Field(min_length=6, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    note: str | None = Field(default=None, max_length=500)


class RejectRefundIn(BaseModel):
    note: str = Field(min_length=10, max_length=500, description="Shown to the runner.")


class CreateRefundIn(BaseModel):
    note: str = Field(min_length=10, max_length=500)