from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.modules.auth.models import Role, User
from app.modules.notifications.models import Notification
from app.modules.support import service as support_service
from app.modules.support.models import SupportMessage, SupportStatus, SupportTopic

S = "/api/v1/support"
A = "/api/v1/admin"
MESSAGE = {
    "name": "Wanjiku Kamau", "email": "wanjiku@example.com", "topic": "payment",
    "message": "I paid but my registration still says awaiting payment.",
}


def signup(c, email, name="Test User"):
    res = c.post("/api/v1/auth/signup", json={"full_name": name, "email": email, "password": "correct-horse-1"})
    assert res.status_code == 201


def make_admin(db, email="admin@example.com"):
    c = TestClient(app)
    signup(c, email, "Admin")
    db.scalars(select(User).where(User.email == email)).first().role = Role.admin
    db.commit()
    return c


def alerts(db):
    return [n for n in db.scalars(select(Notification)) if n.dedupe_key.startswith("support_alert")]


def code(res):
    return res.json()["detail"]["code"]


def test_anyone_can_send_a_message_and_admins_are_alerted(client, db):
    make_admin(db)
    res = client.post(S, json=MESSAGE)
    assert res.status_code == 202
    body = res.json()
    assert len(body["reference"]) == 8 and "reply by email" in body["message"]
    stored = db.scalars(select(SupportMessage)).first()
    assert stored.user_id is None and stored.status == SupportStatus.open and stored.topic == SupportTopic.payment
    sent = alerts(db)
    assert len(sent) == 1 and sent[0].to_address == "admin@example.com"
    assert MESSAGE["message"] in sent[0].body_text and body["reference"] in sent[0].subject


def test_a_logged_in_users_message_is_linked_and_bots_are_ignored(client, db):
    make_admin(db)
    signup(client, "runner@example.com")
    assert client.post(S, json=MESSAGE).status_code == 202
    user = db.scalars(select(User).where(User.email == "runner@example.com")).first()
    assert db.scalars(select(SupportMessage)).first().user_id == user.id

    before = len(db.scalars(select(SupportMessage)).all())
    res = TestClient(app).post(S, json={**MESSAGE, "email": "bot@example.com", "website": "http://spam.example"})
    assert res.status_code == 202                       # the bot is told it worked
    assert len(db.scalars(select(SupportMessage)).all()) == before
    assert len(alerts(db)) == 1


def test_messages_are_validated_and_rate_limited(client):
    for bad in (
        {**MESSAGE, "message": "too short"},
        {**MESSAGE, "email": "nope"},
        {**MESSAGE, "topic": "weather"},
        {**MESSAGE, "name": "A"},
        {**MESSAGE, "message": "x" * 2001},
    ):
        assert client.post(S, json=bad).status_code == 422
    for _ in range(3):
        assert client.post(S, json=MESSAGE).status_code == 202
    res = client.post(S, json=MESSAGE)
    assert res.status_code == 429 and code(res) == "rate_limited"


def test_only_admins_can_read_the_inbox(client, db):
    admin = make_admin(db)
    assert TestClient(app).get(f"{A}/support").status_code == 401
    signup(client, "runner@example.com")
    assert client.get(f"{A}/support").status_code == 403
    assert admin.get(f"{A}/support").status_code == 200


def test_admins_can_work_the_inbox(client, db):
    admin = make_admin(db)
    client.post(S, json=MESSAGE)
    assert admin.get(f"{A}/summary").json()["support_open"] == 1
    inbox = admin.get(f"{A}/support?status=open").json()
    assert inbox["total"] == 1 and inbox["items"][0]["message"] == MESSAGE["message"]

    mid = inbox["items"][0]["id"]
    res = admin.post(f"{A}/support/{mid}/resolve", json={"note": "Replied by email with the receipt."})
    assert res.status_code == 200
    done = res.json()
    assert done["status"] == "resolved" and done["resolved_by_name"] == "Admin"
    assert admin.get(f"{A}/summary").json()["support_open"] == 0
    assert admin.get(f"{A}/support?status=open").json()["total"] == 0
    assert admin.get(f"{A}/support?status=resolved").json()["total"] == 1
    again = admin.post(f"{A}/support/{mid}/resolve", json={})
    assert again.status_code == 409 and code(again) == "already_resolved"


def test_old_resolved_messages_are_purged_but_open_ones_are_kept(db):
    old = datetime.now(timezone.utc) - timedelta(days=400)
    db.add(SupportMessage(
        name="A B", email="a@example.com", topic=SupportTopic.other, message="Old and resolved.",
        status=SupportStatus.resolved, resolved_at=old, created_at=old,
    ))
    db.add(SupportMessage(
        name="C D", email="c@example.com", topic=SupportTopic.other, message="Old but still open.", created_at=old,
    ))
    db.commit()
    assert support_service.purge_resolved(db, days=365) == 1
    left = db.scalars(select(SupportMessage)).all()
    assert [m.message for m in left] == ["Old but still open."]