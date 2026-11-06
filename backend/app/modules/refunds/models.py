import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefundStatus(str, enum.Enum):
    requested = "requested"
    paid = "paid"
    rejected = "rejected"


class RefundReason(str, enum.Enum):
    runner_cancelled = "runner_cancelled"
    event_cancelled = "event_cancelled"
    late_payment = "late_payment"
    admin = "admin"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (
        # one live (not rejected) refund per payment
        Index(
            "uq_refund_active_per_payment",
            "payment_id",
            unique=True,
            postgresql_where=text("status <> 'rejected'"),
            sqlite_where=text("status <> 'rejected'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"), index=True)
    registration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registrations.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    phone: Mapped[str] = mapped_column(String(20))               # where the money goes: the number that paid
    reason: Mapped[RefundReason] = mapped_column(
        Enum(RefundReason, name="refund_reason", native_enum=False, length=20)
    )
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status", native_enum=False, length=10), default=RefundStatus.requested
    )
    mpesa_reference: Mapped[str | None] = mapped_column(String(30), unique=True)    # the outgoing transaction's code
    admin_note: Mapped[str | None] = mapped_column(String(500))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))