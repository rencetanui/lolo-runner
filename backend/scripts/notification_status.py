"""  python -m scripts.notification_status
     python -m scripts.notification_status --requeue-failed   (after fixing credentials)"""
import argparse
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from app.db.session import SessionLocal
from app.modules.auth import models as _auth  # noqa: F401
from app.modules.notifications.models import Notification, NotificationStatus

parser = argparse.ArgumentParser()
parser.add_argument("--requeue-failed", action="store_true")
args = parser.parse_args()

with SessionLocal() as db:
    if args.requeue_failed:
        n = db.execute(
            update(Notification)
            .where(Notification.status == NotificationStatus.failed)
            .values(status=NotificationStatus.pending, attempts=0, last_error=None,
                    next_attempt_at=datetime.now(timezone.utc))
        ).rowcount
        db.commit()
        print(f"Re-queued {n} failed notification(s)")

    print("\nBy status:")
    for status, channel, count in db.execute(
        select(Notification.status, Notification.channel, func.count()).group_by(Notification.status, Notification.channel)
    ):
        print(f"  {status.value:8} {channel.value:6} {count}")

    print("\nMost recent problems:")
    problems = db.scalars(
        select(Notification).where(Notification.last_error.is_not(None))
        .order_by(Notification.created_at.desc()).limit(10)
    ).all()
    for p in problems or []:
        print(f"  [{p.status.value}] {p.channel.value} to {p.to_address}: {p.last_error}")
    if not problems:
        print("  none")