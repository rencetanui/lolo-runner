import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.exc import IntegrityError

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import DUMMY_HASH, hash_password, verify_password
from app.modules.notifications import service as notifications

from .models import AuthToken, RateLimit, TokenPurpose, User, UserIdentity
from .schemas import SignupIn

log = logging.getLogger("security")


class EmailTakenError(Exception):
    pass


class AuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email.lower())).first()


# ------------------------------------------------------------------ tokens
def issue_token(db: Session, user: User, purpose: TokenPurpose, ttl: timedelta) -> tuple[str, AuthToken]:
    """Create a new token and cancel any earlier unused ones of the same kind. Doesn't commit."""
    now = _now()
    db.execute(
        update(AuthToken)
        .where(AuthToken.user_id == user.id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw = secrets.token_urlsafe(32)
    row = AuthToken(user_id=user.id, purpose=purpose, token_hash=_hash_token(raw), expires_at=now + ttl)
    db.add(row)
    db.flush()
    return raw, row


def _usable_token(db: Session, raw: str, purpose: TokenPurpose) -> AuthToken | None:
    return db.scalars(
        select(AuthToken)
        .where(
            AuthToken.token_hash == _hash_token(raw),
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > _now(),
        )
        .with_for_update()
    ).first()


# ------------------------------------------------------------------ signup, login
def send_verification_email(db: Session, user: User) -> bool:
    """Queue a fresh verification link. Doesn't commit."""
    if user.email_verified:
        return False
    hours = settings.verify_token_hours
    raw, row = issue_token(db, user, TokenPurpose.email_verify, timedelta(hours=hours))
    notifications.notify_email_verification(db, user, raw, row.id, hours)
    return True


def create_user(db: Session, data: SignupIn) -> User:
    if get_by_email(db, data.email):
        raise EmailTakenError
    user = User(
        full_name=data.full_name.strip(),
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.flush()
    if settings.require_email_verification:
        send_verification_email(db, user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_by_email(db, email)
    if not user:
        verify_password(password, DUMMY_HASH)  # same work either way
        return None
    if not verify_password(password, user.hashed_password) or not user.is_active:
        return None
    return user


# ------------------------------------------------------------------ email verification
def verify_email(db: Session, raw_token: str) -> User:
    token = _usable_token(db, raw_token, TokenPurpose.email_verify)
    if token is None:
        # A link opened twice (or touched by a mail scanner) must not look like a failure.
        used = db.scalars(
            select(AuthToken).where(
                AuthToken.token_hash == _hash_token(raw_token),
                AuthToken.purpose == TokenPurpose.email_verify,
                AuthToken.used_at.is_not(None),
            )
        ).first()
        user = db.get(User, used.user_id) if used else None
        if user and user.email_verified:
            return user
        raise AuthError("invalid_token", "This verification link is invalid or has expired. Please request a new one.")
    user = db.get(User, token.user_id)
    now = _now()
    token.used_at = now
    if user and not user.email_verified_at:
        user.email_verified_at = now
    db.commit()
    return user


# ------------------------------------------------------------------ passwords
def request_password_reset(db: Session, email: str, *, may_send: bool) -> None:
    """Always returns quietly: the caller must not learn whether the account exists."""
    user = get_by_email(db, email)
    if user is None or not user.is_active or not may_send:
        return
    minutes = settings.reset_token_minutes
    raw, row = issue_token(db, user, TokenPurpose.password_reset, timedelta(minutes=minutes))
    notifications.notify_password_reset(db, user, raw, row.id, minutes)
    db.commit()
    log.info("password reset requested user=%s", user.id)


def reset_password(db: Session, raw_token: str, new_password: str) -> None:
    invalid = AuthError("invalid_token", "This reset link is invalid or has expired. Please request a new one.")
    token = _usable_token(db, raw_token, TokenPurpose.password_reset)
    if token is None:
        raise invalid
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise invalid

    now = _now()
    user.hashed_password = hash_password(new_password)
    user.has_password = True
    user.token_version += 1                        # signs out every existing session
    if not user.email_verified_at:
        user.email_verified_at = now               # they just proved they control the inbox
    token.used_at = now
    db.execute(
        update(AuthToken)
        .where(AuthToken.user_id == user.id, AuthToken.purpose == TokenPurpose.password_reset, AuthToken.used_at.is_(None))
        .values(used_at=now)
    )
    notifications.notify_password_changed(db, user)
    db.commit()
    log.info("password reset completed user=%s", user.id)


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.hashed_password):
        raise AuthError("incorrect_password", "Your current password is incorrect.")
    if verify_password(new_password, user.hashed_password):
        raise AuthError("same_password", "Your new password must be different from the current one.")
    user.hashed_password = hash_password(new_password)
    user.has_password = True
    user.token_version += 1
    notifications.notify_password_changed(db, user)
    db.commit()
    db.refresh(user)
    log.info("password changed user=%s", user.id)


# ------------------------------------------------------------------ housekeeping
def purge_expired(db: Session) -> dict:
    """Worker job: remove old tokens and rate-limit counters. Commits."""
    cutoff = _now() - timedelta(days=7)
    tokens = db.execute(
        delete(AuthToken).where(or_(AuthToken.expires_at < cutoff, AuthToken.used_at < cutoff))
    ).rowcount
    limits = db.execute(delete(RateLimit).where(RateLimit.window_start < int(time.time()) - 2 * 86400)).rowcount
    db.commit()
    return {"tokens": tokens or 0, "rate_limits": limits or 0}

# ------------------------------------------------------------------ Google sign-in
GOOGLE = "google"


def verify_google_credential(credential: str) -> dict:
    """Check the signature, audience (our client id) and expiry of a Google ID token."""
    try:
        info = google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), settings.google_client_id, clock_skew_in_seconds=10
        )
    except ValueError:
        raise AuthError("invalid_google_token", "We couldn't verify your Google sign-in. Please try again.", 401)
    except Exception:
        log.exception("Could not verify a Google credential")
        raise AuthError("google_unavailable", "Google sign-in isn't available right now. Please try again shortly.", 503)
    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise AuthError("invalid_google_token", "We couldn't verify your Google sign-in. Please try again.", 401)
    return info


def _truthy(value) -> bool:
    return value is True or str(value).lower() == "true"


def _google_is_authoritative(info: dict) -> bool:
    """Google vouches for Gmail addresses and Workspace domains. For any other address it doesn't."""
    email = str(info.get("email", "")).lower()
    return _truthy(info.get("email_verified")) and (email.endswith("@gmail.com") or bool(info.get("hd")))


def _display_name(info: dict, email: str) -> str:
    name = " ".join(str(info.get("name") or "").split())[:100]
    return name if len(name) >= 2 else email.split("@")[0][:100]


def google_sign_in(db: Session, credential: str, *, _retry: bool = True) -> User:
    info = verify_google_credential(credential)
    sub = str(info.get("sub") or "")
    email = str(info.get("email") or "").lower()
    if not sub or not email or not _truthy(info.get("email_verified")):
        raise AuthError(
            "google_email_unverified",
            "Your Google account doesn't have a verified email address, so we can't use it to sign in.",
            400,
        )
    authoritative = _google_is_authoritative(info)
    disabled = AuthError("account_disabled", "This account has been disabled.", 403)

    try:
        identity = db.scalars(
            select(UserIdentity).where(UserIdentity.provider == GOOGLE, UserIdentity.provider_user_id == sub)
        ).first()
        if identity:
            user = db.get(User, identity.user_id)
            if user is None or not user.is_active:
                raise disabled
            return user

        user = get_by_email(db, email)
        if user:
            if not user.is_active:
                raise disabled
            if not authoritative:
                raise AuthError(
                    "account_exists",
                    "An account with this email already exists. Please log in with your password.",
                    409,
                )
            if not user.email_verified_at:
                # Whoever registered this address never proved they own it. Google just proved who does,
                # so shut out the password and sessions of whoever created the account first.
                user.hashed_password = hash_password(secrets.token_urlsafe(32))
                user.has_password = False
                user.token_version += 1
                user.email_verified_at = _now()
            db.add(UserIdentity(user_id=user.id, provider=GOOGLE, provider_user_id=sub, email_at_link=email))
            notifications.notify_google_linked(db, user)
            db.commit()
            log.info("google linked user=%s", user.id)
            return user

        user = User(
            full_name=_display_name(info, email),
            email=email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            has_password=False,
            email_verified_at=_now() if authoritative else None,
        )
        db.add(user)
        db.flush()
        db.add(UserIdentity(user_id=user.id, provider=GOOGLE, provider_user_id=sub, email_at_link=email))
        if not authoritative and settings.require_email_verification:
            send_verification_email(db, user)
        db.commit()
        db.refresh(user)
        log.info("google signup user=%s", user.id)
        return user
    except IntegrityError:           # two sign-ins for a new account raced each other
        db.rollback()
        if _retry:
            return google_sign_in(db, credential, _retry=False)
        raise