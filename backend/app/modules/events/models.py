import enum
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EventStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    cancelled = "cancelled"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150))
    event_date: Mapped[date] = mapped_column(index=True)
    location: Mapped[str] = mapped_column(String(150))
    registration_opens: Mapped[date]
    registration_closes: Mapped[date]
    refunds_until: Mapped[date | None]
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    venue_details: Mapped[str | None] = mapped_column(Text)
    map_url: Mapped[str | None] = mapped_column(String(500))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    banner_file: Mapped[str | None] = mapped_column(String(40))      # random key of the uploaded banner

    @property
    def banner_url(self) -> str | None:
        return f"/media/events/{self.banner_file}.jpg" if self.banner_file else None
    
    # Existing and seeded events stay public; the organizer API always creates drafts explicitly.
    # native_enum=False stores plain text, so no Postgres enum type has to be created in the migration.
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status", native_enum=False, length=20),
        default=EventStatus.published,
        server_default=EventStatus.published.value,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    distances: Mapped[list["Distance"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="Distance.km",
    )


class Distance(Base):
    __tablename__ = "distances"
    __table_args__ = (UniqueConstraint("event_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(30))
    km: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    capacity: Mapped[int]
    min_age: Mapped[int] = mapped_column(default=12)
    start_time: Mapped[time | None]                  # Nairobi local time
    cutoff_minutes: Mapped[int | None]
    
    event: Mapped["Event"] = relationship(back_populates="distances")