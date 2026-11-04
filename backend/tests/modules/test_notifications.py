from datetime import datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.modules.auth.models import Role, User
from app.modules.notifications import service as notifications
from app.modules.notifications.models import Channel, Notification, NotificationStatus
from app.modules.notifications.providers.base import PermanentSendError, SendError
from app.modules.notifications.service import MAX_ATTEMPTS
from app.modules.payments import service as payments
from app.modules.payments.models import Payment
from app.modules.registrations.waiver import WAIVER_VERSION
from app.utils.dates import KENYA_TZ, today_ke

PROFILE = {
    "date_of_birth": "1990-05-14",
    "gender": "female",
    "phone": "0712345678",
    "tshirt_size": "M",
    "emergency_contact_name": "Mary Kamau",
    "emergency_contact_phone": "0722000111",
    "emergency_contact_relationship": "Sister",
}
ZERO = {"sent": 0, "retry": 0, "failed": 0}


class FakeEmail:
    def __init__(self):
        self.sent, self.error = [], None

    def send(self, *, to, subject, text, html=None):
        if self.error:
            raise self.error
        self.sent.append({"to": to, "subject": subject, "text": text, "html": html})
        return None


class FakeSms:
    def __init__(self):
        self.sent, self.error = [], None

    def send(self, *, to, message):
        if self.error:
            raise self.error
        self.sent.append({"to": to, "message": message})
        return "ref-1"


@pytest.fixture
def fake_email():
    return FakeEmail()


@pytest.fixture
def fake_sms():
    return FakeSms()


def signup(c, address, name="Wanjiku Kamau"):
    res = c.post("/api/v1/auth/signup", json={"full_name": name, "email": address, "password": "correct-horse-1"})
    assert res.status_code == 201
    assert c.put("/api/v1/runners/me", json=PROFILE).status_code == 200


def free_event(make_event, db, **kwargs):
    event = make_event(**kwargs)
    for distance in event.distances:
        distance.fee = 0
    db.commit()
    return event


def register(c, event, index=0):
    res = c.post(
        f"/api/v1/events/{event.id}/registrations",
        json={"distance_id": str(event.distances[index].id), "waiver_version": WAIVER_VERSION},
    )
    assert res.status_code == 201, res.text
    return res.json()


def queued(db):
    return list(db.scalars(select(Notification).order_by(Notification.created_at)))


def pay(c, registration_id):
    return c.post(f"/api/v1/registrations/{registration_id}/payments", json={"phone": None})


def stk_callback(checkout_id, amount=500):
    stk = {
        "MerchantRequestID": "m_1",
        "CheckoutRequestID": checkout_id,
        "ResultCode": 0,
        "ResultDesc": "The service request is processed successfully.",
        "CallbackMetadata": {"Item": [
            {"Name": "Amount", "Value": amount},
            {"Name": "MpesaReceiptNumber", "Value": "QGR7XYZ123"},
            {"Name": "PhoneNumber", "Value": 254712345678},
        ]},
    }
    return TestClient(app).post("/api/v1/payments/callbacks/stk/test-secret", json={"Body": {"stkCallback": stk}})


def test_free_registration_queues_an_email_and_an_sms(client, make_event, db):
    event = free_event(make_event, db)
    signup(client, "a@example.com")
    register(client, event)
    rows = queued(db)
    assert {(n.channel, n.to_address) for n in rows} == {
        (Channel.email, "a@example.com"),
        (Channel.sms, "+254712345678"),
    }
    assert all(n.status == NotificationStatus.pending for n in rows)


def test_paid_registration_is_announced_only_once_payment_succeeds(client, make_event, db, mpesa, monkeypatch):
    monkeypatch.setattr(settings, "mpesa_callback_secret", "test-secret")
    event = make_event()
    signup(client, "a@example.com")
    reg = register(client, event)
    assert queued(db) == []                         # unpaid: nothing yet

    assert pay(client, reg["id"]).status_code == 201
    assert queued(db) == []                         # prompt sent: still nothing
    assert stk_callback("ws_CO_1").status_code == 200

    rows = queued(db)
    assert len(rows) == 2
    email = next(n for n in rows if n.channel == Channel.email)
    assert "QGR7XYZ123" in email.body_text and "KES 500" in email.body_text

    assert stk_callback("ws_CO_1").status_code == 200   # a repeated callback adds nothing
    assert len(queued(db)) == 2


def test_cancellation_sends_an_email_only(client, make_event, db):
    event = free_event(make_event, db)
    signup(client, "a@example.com")
    reg = register(client, event)
    assert client.delete(f"/api/v1/registrations/{reg['id']}").status_code == 200
    kinds = {(n.channel, n.dedupe_key.split(":")[0]) for n in queued(db)}
    assert (Channel.email, "registration_cancelled") in kinds
    assert (Channel.sms, "registration_cancelled") not in kinds


def test_new_date_or_location_notifies_registered_runners_only(client, make_event, db):
    event = free_event(make_event, db)
    stays = TestClient(app)
    signup(stays, "stays@example.com")
    register(stays, event)
    leaves = TestClient(app)
    signup(leaves, "leaves@example.com")
    gone = register(leaves, event)
    leaves.delete(f"/api/v1/registrations/{gone['id']}")

    admin = TestClient(app)
    signup(admin, "admin@example.com")
    db.scalars(select(User).where(User.email == "admin@example.com")).first().role = Role.admin
    db.commit()

    url = f"/api/v1/organizer/events/{event.id}"
    before = len(queued(db))
    assert admin.patch(url, json={"name": "Renamed Run"}).status_code == 200
    assert len(queued(db)) == before                # a new name alone isn't worth a message

    assert admin.patch(url, json={"location": "Naivasha"}).status_code == 200
    new = [n for n in queued(db) if n.dedupe_key.startswith("event_changed")]
    assert len(new) == 2
    assert {n.channel for n in new} == {Channel.email, Channel.sms}
    assert next(n for n in new if n.channel == Channel.email).to_address == "stays@example.com"
    assert "Naivasha" in new[0].body_text


def test_worker_delivers_queued_messages(client, make_event, db, fake_email, fake_sms):
    event = free_event(make_event, db, name="Nakuru Sunrise Run")
    signup(client, "a@example.com")
    register(client, event)

    assert notifications.process_due(db, fake_email, fake_sms) == {"sent": 2, "retry": 0, "failed": 0}
    assert "Nakuru Sunrise Run" in fake_email.sent[0]["text"]
    sms = fake_sms.sent[0]["message"]
    assert len(sms) <= 160 and sms.isascii()
    assert all(n.status == NotificationStatus.sent for n in queued(db))
    assert notifications.process_due(db, fake_email, fake_sms) == ZERO


def test_temporary_failures_back_off_then_give_up(client, make_event, db, fake_email, fake_sms):
    event = free_event(make_event, db)
    signup(client, "a@example.com")
    register(client, event)
    fake_email.error = SendError("smtp down")

    result = notifications.process_due(db, fake_email, fake_sms)
    assert result == {"sent": 1, "retry": 1, "failed": 0}      # the SMS went, the email will retry
    row = next(n for n in queued(db) if n.channel == Channel.email)
    assert row.status == NotificationStatus.pending and row.attempts == 1 and row.last_error == "smtp down"
    assert notifications.process_due(db, fake_email, fake_sms) == ZERO   # backoff: not due yet

    for _ in range(MAX_ATTEMPTS - 1):
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        notifications.process_due(db, fake_email, fake_sms)
    db.refresh(row)
    assert row.status == NotificationStatus.failed and row.attempts == MAX_ATTEMPTS


def test_permanent_failures_are_not_retried(client, make_event, db, fake_email, fake_sms):
    event = free_event(make_event, db)
    signup(client, "a@example.com")
    register(client, event)
    fake_sms.error = PermanentSendError("invalid number")

    assert notifications.process_due(db, fake_email, fake_sms) == {"sent": 1, "retry": 0, "failed": 1}
    row = next(n for n in queued(db) if n.channel == Channel.sms)
    assert row.status == NotificationStatus.failed and row.attempts == 1


def test_user_supplied_text_is_escaped_in_email_html(client, make_event, db):
    event = free_event(make_event, db, name="<script>alert(1)</script> & Co")
    signup(client, "a@example.com")
    register(client, event)
    html = next(n for n in queued(db) if n.channel == Channel.email).body_html
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_reminders_go_out_the_day_before_and_only_in_daytime(client, make_event, db):
    event = free_event(make_event, db)
    signup(client, "a@example.com")
    register(client, event)
    event.event_date = today_ke() + timedelta(days=1)
    db.commit()
    before = len(queued(db))

    night = datetime.combine(today_ke(), time(3, 0), tzinfo=KENYA_TZ)
    morning = datetime.combine(today_ke(), time(9, 0), tzinfo=KENYA_TZ)
    assert notifications.enqueue_event_reminders(db, now=night) == 0
    assert notifications.enqueue_event_reminders(db, now=morning) == 2
    assert notifications.enqueue_event_reminders(db, now=morning) == 0      # never twice
    assert len(queued(db)) == before + 2


def test_messages_stuck_in_sending_are_picked_up_again(client, make_event, db, fake_email, fake_sms):
    event = free_event(make_event, db)
    signup(client, "a@example.com")
    register(client, event)
    row = next(n for n in queued(db) if n.channel == Channel.email)
    row.status = NotificationStatus.sending                       # a worker died holding this one
    row.lease_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert notifications.process_due(db, fake_email, fake_sms)["sent"] == 2


def test_old_delivered_messages_are_purged_but_pending_ones_are_kept(client, make_event, db, fake_email, fake_sms):
    event = free_event(make_event, db)
    signup(client, "a@example.com")
    register(client, event)
    notifications.process_due(db, fake_email, fake_sms)
    old = datetime.now(timezone.utc) - timedelta(days=100)
    sent_row, other = queued(db)
    sent_row.created_at = old
    other.created_at = old
    other.status = NotificationStatus.pending
    db.commit()

    assert notifications.purge_old(db, days=90) == 1
    assert len(queued(db)) == 1


def test_worker_settles_payments_whose_callback_never_arrived(client, make_event, db, mpesa):
    event = make_event()
    signup(client, "a@example.com")
    reg = register(client, event)
    assert pay(client, reg["id"]).status_code == 201
    payment = db.scalars(select(Payment)).first()
    payment.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()

    mpesa.query_result = {"ResultCode": "0", "ResultDesc": "ok"}
    assert payments.reconcile_pending(db, mpesa) == {"abandoned": 0, "settled": 1}
    assert client.get(f"/api/v1/registrations/{reg['id']}").json()["status"] == "confirmed"
    assert {n.channel for n in queued(db)} == {Channel.email, Channel.sms}