import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, func, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Role(str, enum.Enum):
    runner = "runner"
    organizer = "organizer"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), default=Role.runner)
    is_active: Mapped[bool] = mapped_column(default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Bumped on every password change. Sessions carry the number they were issued with.
    token_version: Mapped[int] = mapped_column(default=0, server_default="0")
    # False for accounts created through Google: they have a random password nobody knows.
    has_password: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None


class TokenPurpose(str, enum.Enum):
    password_reset = "password_reset"
    email_verify = "email_verify"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[TokenPurpose] = mapped_column(
        Enum(TokenPurpose, name="token_purpose", native_enum=False, length=20)
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)     # SHA-256 of the emailed token
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RateLimit(Base):
    __tablename__ = "rate_limits"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)       # hash of scope + identifier
    window_start: Mapped[int] = mapped_column(BigInteger, primary_key=True)   # unix seconds
    hits: Mapped[int] = mapped_column(default=0)
    
class UserIdentity(Base):
    """A way to log in that lives outside our password system. Today: Google."""
    __tablename__ = "user_identities"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_user_id: Mapped[str] = mapped_column(String(255))     # Google's stable "sub"
    email_at_link: Mapped[str] = mapped_column(String(255))        # a record only: emails can change
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)