import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from .models import RefundReason, RefundStatus


class CancellationPreviewOut(BaseModel):
    paid: bool
    refundable: bool
    amount: Decimal | None
    refunds_until: date | None


class RefundOut(BaseModel):
    id: uuid.UUID
    status: RefundStatus
    reason: RefundReason
    amount: Decimal
    phone: str
    created_at: datetime
    decided_at: datetime | None
    mpesa_reference: str | None
    message: str | None          # the reason, shown only when a refund was rejected