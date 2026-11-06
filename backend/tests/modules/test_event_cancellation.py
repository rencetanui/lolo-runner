from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.modules.auth.models import Role, User
from app.modules.notifications.models import Notification
from app.modules.refunds.models import Refund, RefundReason
from app.modules.registrations.waiver import WAIVER_VERSION
from app.utils.dates import today_ke

O = "/api/v1/organizer/events"
REASON = "The venue is no longer available."
PROFILE = {
    "date_of_birth": "1990-05-14", "gender": "female", "phone": "0712345678", "tshirt_size": "M",
    "emergency_contact_name": "Mary Kamau", "emergency_contact_phone": "0722000111",
    "emergency_contact_relationship": "Sister",
}


@pytest.fixture(autouse=True)
def callback_secret(monkeypatch):
    monkeypatch.setattr(settings, "mpesa_callback_secret", "test-secret")


def signup(c, email, name="Test Runner"):
    res = c.post("/api/v1/auth/signup", json={"full_name": name, "email": email, "password": "correct-horse-1"})
    assert res.status_code == 201
    assert c.put("/api/v1/runners/me", json=PROFILE).status_code == 200


def promote(db, email, role):
    db.scalars(select(User).where(User.email == email)).first().role = role
    db.commit()


def make_admin(db, email="admin@example.com"):
    c = TestClient(app)
    signup(c, email, "Admin")
    promote(db, email, Role.admin)
    return c


def register(c, event, index=0):
    res = c.post(
        f"/api/v1/events/{event.id}/registrations",
        json={"distance_id": str(event.distances[index].id), "waiver_version": WAIVER_VERSION},
    )
    assert res.status_code == 201, res.text
    return res.json()


def pay_and_confirm(c, reg_id, mpesa):
    assert c.post(f"/api/v1/registrations/{reg_id}/payments", json={"phone": None}).status_code == 201
    stk = {"MerchantRequestID": "m_1", "CheckoutRequestID": f"ws_CO_{len(mpesa.pushes)}", "ResultCode": 0,
           "ResultDesc": "ok", "CallbackMetadata": {"Item": [
               {"Name": "Amount", "Value": 500}, {"Name": "MpesaReceiptNumber", "Value": "QGR7XYZ123"}]}}
    res = TestClient(app).post("/api/v1/payments/callbacks/stk/test-secret", json={"Body": {"stkCallback": stk}})
    assert res.status_code == 200


def reg_status(c, reg_id):
    return c.get(f"/api/v1/registrations/{reg_id}").json()["status"]


def code(res):
    return res.json()["detail"]["code"]


def notes(db, kind):
    return [n for n in db.scalars(select(Notification)) if n.dedupe_key.startswith(kind)]


def event_payload():
    today = date.today()
    return {
        "name": "Draft Run", "event_date": (today + timedelta(days=60)).isoformat(), "location": "Nakuru",
        "registration_opens": (today - timedelta(days=1)).isoformat(),
        "registration_closes": (today + timedelta(days=50)).isoformat(),
        "distances": [{"name": "5K", "km": 5, "fee": 500, "capacity": 5}],
    }


@pytest.fixture
def scenario(client, make_event, mpesa, db):
    """a paid, b reserved but unpaid, c on a free distance. admin cancels nothing yet."""
    admin = make_admin(db)
    event = make_event()
    event.distances[1].fee = 0
    db.commit()
    a, b, c = TestClient(app), TestClient(app), TestClient(app)
    signup(a, "a@example.com"); signup(b, "b@example.com"); signup(c, "c@example.com")
    ra = register(a, event, 0)
    pay_and_confirm(a, ra["id"], mpesa)
    rb = register(b, event, 0)
    rc = register(c, event, 1)
    return {"admin": admin, "event": event, "runners": [(a, ra), (b, rb), (c, rc)]}


def test_cancelling_an_event_cancels_everything_refunds_the_paid_and_tells_everyone(scenario, db):
    admin, event = scenario["admin"], scenario["event"]
    res = admin.post(f"{O}/{event.id}/cancel", json={"reason": REASON})
    assert res.status_code == 200 and res.json()["status"] == "cancelled"

    for runner, reg in scenario["runners"]:
        assert reg_status(runner, reg["id"]) == "cancelled"
    refunds = db.scalars(select(Refund)).all()
    assert len(refunds) == 1 and refunds[0].reason == RefundReason.event_cancelled and int(refunds[0].amount) == 500

    sent = notes(db, "event_cancelled")
    assert len(sent) == 6                                   # three runners, an email and an SMS each
    email = {n.to_address: n for n in sent if n.channel.value == "email"}
    assert "refunded" in email["a@example.com"].body_text and REASON in email["a@example.com"].body_text
    assert "refund" not in email["b@example.com"].body_text.lower()
    assert "refund" not in email["c@example.com"].body_text.lower()
    assert len(notes(db, "refunds_queued")) == 1            # the admin is told once


def test_the_cancel_preview_counts_what_will_happen(scenario):
    body = scenario["admin"].get(f"{O}/{scenario['event'].id}/cancel-preview").json()
    assert body["registrations"] == 3 and body["paid_registrations"] == 1
    assert float(body["refund_total"]) == 500


def test_a_cancelled_event_leaves_the_list_but_its_page_explains(scenario):
    admin, event = scenario["admin"], scenario["event"]
    public = TestClient(app)
    assert len(public.get("/api/v1/events").json()) == 1
    admin.post(f"{O}/{event.id}/cancel", json={"reason": REASON})
    assert public.get("/api/v1/events").json() == []
    page = public.get(f"/api/v1/events/{event.id}").json()
    assert page["status"] == "cancelled" and page["cancellation_reason"] == REASON


def test_nobody_can_register_for_a_cancelled_event(scenario):
    admin, event = scenario["admin"], scenario["event"]
    admin.post(f"{O}/{event.id}/cancel", json={"reason": REASON})
    runner = TestClient(app)
    signup(runner, "late@example.com")
    res = runner.post(
        f"/api/v1/events/{event.id}/registrations",
        json={"distance_id": str(event.distances[0].id), "waiver_version": WAIVER_VERSION},
    )
    assert res.status_code == 409 and code(res) == "event_cancelled"
    assert runner.get(f"/api/v1/events/{event.id}/availability").status_code == 409


def test_cancelled_events_cannot_be_edited_or_cancelled_again(scenario):
    admin, event = scenario["admin"], scenario["event"]
    admin.post(f"{O}/{event.id}/cancel", json={"reason": REASON})
    url = f"{O}/{event.id}"
    assert admin.patch(url, json={"name": "New name"}).status_code == 409
    res = admin.post(f"{url}/publish")
    assert res.status_code == 409 and code(res) == "event_cancelled"
    assert admin.post(f"{url}/distances", json={"name": "3K", "km": 3, "fee": 0, "capacity": 5}).status_code == 409
    assert admin.post(f"{url}/cancel", json={"reason": "Cancelling a second time."}).status_code == 409


def test_only_published_future_events_can_be_cancelled(client, make_event, db):
    admin = make_admin(db)
    draft = admin.post(O, json=event_payload()).json()
    res = admin.post(f"{O}/{draft['id']}/cancel", json={"reason": "A draft is deleted instead."})
    assert res.status_code == 409 and code(res) == "not_published"

    past = make_event()
    past.event_date = today_ke() - timedelta(days=1)
    db.commit()
    res = admin.post(f"{O}/{past.id}/cancel", json={"reason": "It has already happened."})
    assert res.status_code == 422 and code(res) == "event_in_past"
    assert admin.post(f"{O}/{past.id}/cancel", json={"reason": "short"}).status_code == 422


def test_other_organizers_cannot_cancel_it(client, make_event, db):
    event = make_event()
    organizer = TestClient(app)
    signup(organizer, "org@example.com")
    promote(db, "org@example.com", Role.organizer)
    assert organizer.post(f"{O}/{event.id}/cancel", json={"reason": REASON}).status_code == 404
    assert organizer.get(f"{O}/{event.id}/cancel-preview").status_code == 404
    signup(client, "runner@example.com")
    assert client.post(f"{O}/{event.id}/cancel", json={"reason": REASON}).status_code == 403


def test_the_refund_deadline_can_be_set_and_cleared(client, make_event, db):
    admin = make_admin(db)
    event = make_event()                                    # the event is 30 days away
    url = f"{O}/{event.id}"
    until = (today_ke() + timedelta(days=10)).isoformat()
    res = admin.patch(url, json={"refunds_until": until})
    assert res.status_code == 200 and res.json()["refunds_until"] == until
    assert TestClient(app).get(f"/api/v1/events/{event.id}").json()["refunds_until"] == until

    res = admin.patch(url, json={"refunds_until": None})
    assert res.status_code == 200 and res.json()["refunds_until"] is None

    too_late = (today_ke() + timedelta(days=60)).isoformat()
    res = admin.patch(url, json={"refunds_until": too_late})
    assert res.status_code == 422 and code(res) == "invalid_refund_date"