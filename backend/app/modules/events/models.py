import uuid 
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class Event(Base):
    __tablename__ = "events"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150))
    event_date: Mapped[date] = mapped_column(index=True)
    location: Mapped[str] = mapped_column(index=True)
    registration_opens: Mapped[date]    
    registration_closes: Mapped[date]    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    distances: Mapped[list["Distance"]] = relationship(back_populates="event", cascade="all, delete-orphan", order_by="Distance.km")
    
class Distance(Base):
    __tablename__ = "distances"
    __table_args__ = (UniqueConstraint("event_id", "name"),)
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4) 
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(30))       # "5K", "21K"
    km: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # in KES
    capacity: Mapped[int]
    min_age: Mapped[int] = mapped_column(default=12)

    event: Mapped["Event"] = relationship(back_populates="distances")
    