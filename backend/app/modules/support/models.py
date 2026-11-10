import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SupportTopic(str, enum.Enum):
    registration = "registration"
    payment = "payment"
    refund = "refund"
    account = "account"
    event = "event"
    other = "other"


class SupportStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255))
    topic: Mapped[SupportTopic] = mapped_column(
        Enum(SupportTopic, name="support_topic", native_enum=False, length=20)
    )
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[SupportStatus] = mapped_column(
        Enum(SupportStatus, name="support_status", native_enum=False, length=10), default=SupportStatus.open
    )
    admin_note: Mapped[str | None] = mapped_column(String(500))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)