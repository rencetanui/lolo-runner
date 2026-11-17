from datetime import datetime, timedelta, timezone

from app.modules.notifications.models import Channel, Notification, NotificationStatus
from app.modules.ops import service as ops


def test_ready_checks_the_database(client):
    res = client.get("/health/ready")
    assert res.status_code == 200 and res.json() == {"status": "ok"}


def test_worker_health_is_red_until_the_worker_has_reported(client):
    res = client.get("/health/worker")
    assert res.status_code == 503
    assert res.json()["ok"] is False and res.json()["worker_heartbeat_seconds_ago"] is None


def test_worker_health_is_green_after_a_heartbeat(client, db):
    ops.beat(db)
    res = client.get("/health/worker")
    assert res.status_code == 200 and res.json()["ok"] is True


def test_worker_health_goes_red_when_the_heartbeat_goes_stale(client, db):
    ops.beat(db, now=datetime.now(timezone.utc) - timedelta(minutes=10))
    res = client.get("/health/worker")
    assert res.status_code == 503 and res.json()["worker_heartbeat_seconds_ago"] >= 600
    ops.beat(db)
    assert client.get("/health/worker").status_code == 200


def test_worker_health_goes_red_when_messages_pile_up(client, db):
    ops.beat(db)
    stuck = Notification(
        channel=Channel.email, to_address="a@example.com", subject="s", body_text="b", dedupe_key="stuck:1",
        status=NotificationStatus.pending, next_attempt_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    db.add(stuck)
    db.commit()
    res = client.get("/health/worker")
    assert res.status_code == 503 and res.json()["oldest_overdue_notification_seconds"] >= 1800

    stuck.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=30)    # a retry scheduled for later is fine
    db.commit()
    assert client.get("/health/worker").status_code == 200