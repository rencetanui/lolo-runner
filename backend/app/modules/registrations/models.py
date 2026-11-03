import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.events.models import Distance, Event


class RegistrationStatus(str, enum.Enum):
    pending_payment = "pending_payment"
    confirmed = "confirmed"
    cancelled = "cancelled"


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "bib_number"),
        # one non-cancelled registration per runner per event
        Index(
            "uq_registration_active_per_event",
            "user_id",
            "event_id",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
            sqlite_where=text("status <> 'cancelled'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), index=True)
    distance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("distances.id"), index=True)
    bib_number: Mapped[int]
    status: Mapped[RegistrationStatus] = mapped_column(
        Enum(RegistrationStatus, name="registration_status")
    )
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # snapshot at sign-up time
    estimated_finish_minutes: Mapped[int | None]
    waiver_version: Mapped[str] = mapped_column(String(30))
    waiver_accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    guardian_consent: Mapped[bool] = mapped_column(default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    event: Mapped[Event] = relationship(lazy="joined")
    distance: Mapped[Distance] = relationship(lazy="joined")