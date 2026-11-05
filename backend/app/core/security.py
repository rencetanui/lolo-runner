from datetime import datetime, timedelta, timezone

import jwt
import logging
from pwdlib import PasswordHash

from app.core.config import settings

_hasher = PasswordHash.recommended()  # Argon2


log = logging.getLogger("security")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _hasher.verify(password, hashed)


# Used to keep login timing the same whether or not the email exists
DUMMY_HASH = hash_password("not-a-real-password")


def create_access_token(user_id: str, version: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "ver": version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> tuple[str, int] | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        log.warning("session token rejected: %s", type(exc).__name__)
        return None
        
    sub = payload.get("sub")
    version = payload.get("ver")
    
    if sub is None or version is None:
        return None
        
    return (str(sub), int(version))
