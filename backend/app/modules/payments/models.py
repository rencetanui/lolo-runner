import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    needs_review = "needs_review"   # money moved but something didn't match: a human must look


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        # at most one in-flight payment per registration
        Index(
            "uq_payment_pending_per_registration",
            "registration_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    registration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registrations.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(20), default="mpesa")
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    phone: Mapped[str] = mapped_column(String(20))
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), default=PaymentStatus.pending
    )
    merchant_request_id: Mapped[str | None] = mapped_column(String(64))
    checkout_request_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    mpesa_receipt: Mapped[str | None] = mapped_column(String(30), unique=True)
    result_code: Mapped[int | None]
    result_desc: Mapped[str | None] = mapped_column(String(255))
    needs_refund: Mapped[bool] = mapped_column(default=False)
    raw_callback: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))