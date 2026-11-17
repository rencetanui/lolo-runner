from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification, NotificationStatus

from .models import Heartbeat


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def beat(db: Session, name: str = "worker", now: datetime | None = None) -> None:
    now = now or _now()
    insert = postgresql.insert if db.get_bind().dialect.name == "postgresql" else sqlite.insert
    db.execute(
        insert(Heartbeat).values(name=name, beat_at=now)
        .on_conflict_do_update(index_elements=[Heartbeat.name], set_={"beat_at": now})
    )
    db.commit()


def worker_status(db: Session, *, max_beat_age: int = 180, max_queue_age: int = 900, now: datetime | None = None) -> dict:
    """Healthy means: the worker reported recently AND nothing has been waiting to send for a long time."""
    now = now or _now()
    last = db.scalar(select(Heartbeat.beat_at).where(Heartbeat.name == "worker"))
    oldest = db.scalar(
        select(func.min(Notification.next_attempt_at))
        .where(Notification.status == NotificationStatus.pending, Notification.next_attempt_at <= now)
    )
    beat_age = None if last is None else (now - _aware(last)).total_seconds()
    queue_age = None if oldest is None else max((now - _aware(oldest)).total_seconds(), 0.0)
    healthy = beat_age is not None and beat_age <= max_beat_age and (queue_age is None or queue_age <= max_queue_age)
    return {
        "ok": healthy,
        "worker_heartbeat_seconds_ago": None if beat_age is None else round(beat_age),
        "oldest_overdue_notification_seconds": None if queue_age is None else round(queue_age),
    }