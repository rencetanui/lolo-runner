from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Heartbeat(Base):
    """The worker writes a row here every 30 seconds, so an outside check can tell when it has stopped."""
    __tablename__ = "heartbeats"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    beat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))