import enum
import uuid
from datetime import date, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class Gender(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"
    
class TShirtSize(str, enum.Enum):
    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"
    XXL = "XXL"


class RunnerProfile(Base):
    __tablename__ = "runner_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    date_of_birth: Mapped[date]
    gender: Mapped[Gender] = mapped_column(Enum(Gender, name="gender"))
    phone: Mapped[str] = mapped_column(String(20))
    county: Mapped[str | None] = mapped_column(String(60))
    club: Mapped[str | None] = mapped_column(String(100))
    tshirt_size: Mapped[TShirtSize] = mapped_column(Enum(TShirtSize, name="tshirt_size"))
    emergency_contact_name: Mapped[str] = mapped_column(String(100))
    emergency_contact_phone: Mapped[str] = mapped_column(String(20))
    emergency_contact_relationship: Mapped[str] = mapped_column(String(50))
    medical_notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )