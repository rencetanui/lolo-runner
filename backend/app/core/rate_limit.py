import hashlib
import time
from datetime import timedelta

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.models import RateLimit


class RateLimitError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, retry_after)


def client_ip(request: Request) -> str:
    """The caller's address. Forwarded headers are believed only when proxies are configured."""
    peer = request.client.host if request.client else "unknown"
    proxies = settings.trusted_proxies
    forwarded = request.headers.get("x-forwarded-for")
    if proxies > 0 and forwarded:
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[-proxies] if len(hops) >= proxies else hops[0]
    return peer


def _key(scope: str, identifier: str) -> str:
    # Hashed, so the table never holds raw email addresses or IPs.
    return hashlib.sha256(f"{scope}:{identifier}".encode()).hexdigest()


def _window(window: timedelta) -> tuple[int, int]:
    """(start of the current window, seconds left in it)"""
    size = int(window.total_seconds())
    now = int(time.time())
    start = now - now % size
    return start, start + size - now


def _hits(db: Session, key: str, start: int) -> int:
    return db.scalar(select(RateLimit.hits).where(RateLimit.key == key, RateLimit.window_start == start)) or 0


def record(db: Session, scope: str, identifier: str, *, window: timedelta) -> int:
    """Count one event and commit at once, so it's kept even if the request then fails."""
    key = _key(scope, identifier)
    start, _ = _window(window)
    insert = postgresql.insert if db.get_bind().dialect.name == "postgresql" else sqlite.insert
    db.execute(
        insert(RateLimit)
        .values(key=key, window_start=start, hits=1)
        .on_conflict_do_update(
            index_elements=[RateLimit.key, RateLimit.window_start],
            set_={"hits": RateLimit.hits + 1},
        )
    )
    db.commit()
    return _hits(db, key, start)


def check(db: Session, scope: str, identifier: str, *, limit: int, window: timedelta) -> None:
    """Refuse if the limit is already used up. Counts nothing (pair with record() on failure)."""
    start, left = _window(window)
    if _hits(db, _key(scope, identifier), start) >= limit:
        raise RateLimitError(left)


def hit(db: Session, scope: str, identifier: str, *, limit: int, window: timedelta) -> None:
    """Count this request, and refuse it if it goes over the limit."""
    if record(db, scope, identifier, window=window) > limit:
        raise RateLimitError(_window(window)[1])


def allow(db: Session, scope: str, identifier: str, *, limit: int, window: timedelta) -> bool:
    """Like hit(), but answers yes or no instead of raising."""
    return record(db, scope, identifier, window=window) <= limit