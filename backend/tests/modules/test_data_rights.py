import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.auth.models import AuthToken, Role, TokenPurpose, User
from app.modules.events.models import Event
from app.modules.notifications.models import Notification
from app.modules.payments.models import Payment
from app.modules.refunds.models import Refund
from app.modules.registrations.models import Registration
from app.modules.registrations.waiver import WAIVER_VERSION
from app.modules.runners.models import RunnerProfile
from app.modules.support.models import SupportMessage
from app.utils.dates import today_ke

ACCOUNT = "/api/v1/account"
A = "/api/v1/admin"
PASSWORD = "correct-horse-1"
PROFILE = {
    "date_of_birth": "1990-05-14", "gender": "female", "phone": "0712345678", "tshirt_size": "M",
    "emergency_contact_name": "Mary Kamau", "emergency_contact_phone": "0722000111",
    "emergency_contact_relationship": "Sister", "medical_notes": "Asthma",
}


@pytest.fixture(autouse=True)
def callback_secret(monkeypatch):
    monkeypatch.setattr(settings, "mpesa_callback_secret", "test-secret")


def signup(c, email, name="Wanjiku Kamau", profile=True):
    res = c.post("/api/v1/auth/signup", json={"full_name": name, "email": email, "password": PASSWORD})
    assert res.status_code == 201
    if profile:
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


def paid_registration(c, make_event, db, mpesa, email="a@example.com"):
    event = make_event()
    event.refunds_until = today_ke() + timedelta(days=10)
    db.commit()
    signup(c, email)
    reg = register(c, event)
    assert c.post(f"/api/v1/registrations/{reg['id']}/payments", json={"phone": None}).status_code == 201
    checkout = f"ws_CO_{len(mpesa.pushes)}"
    stk = {"MerchantRequestID": "m_1", "CheckoutRequestID": checkout, "ResultCode": 0, "ResultDesc": "ok",
           "CallbackMetadata": {"Item": [
               {"Name": "Amount", "Value": 500}, {"Name": "MpesaReceiptNumber", "Value": "QGR" + checkout.replace("_", "")},
               {"Name": "PhoneNumber", "Value": 254712345678}]}}
    res = TestClient(app).post("/api/v1/payments/callbacks/stk/test-secret", json={"Body": {"stkCallback": stk}})
    assert res.status_code == 200
    return reg


def notes(db, kind):
    return [n for n in db.scalars(select(Notification)) if n.dedupe_key.startswith(kind)]


def token_from(note):
    return re.search(r"token=([\w-]+)", note.body_text).group(1)


def delete_account(c, db):
    assert c.post(f"{ACCOUNT}/delete-request").status_code == 202
    token = token_from(notes(db, "deletion_request")[-1])
    res = c.post(f"{ACCOUNT}/delete-confirm", json={"token": token})
    assert res.status_code == 200, res.text


def code(res):
    return res.json()["detail"]["code"]


def test_the_export_contains_your_data_and_none_of_the_secrets(client, make_event, mpesa, db):
    reg = paid_registration(client, make_event, db, mpesa)
    client.delete(f"/api/v1/registrations/{reg['id']}")          # cancelled inside the window: a refund is requested
    client.post("/api/v1/support", json={
        "name": "Wanjiku", "email": "a@example.com", "topic": "refund", "message": "Where is my refund please?",
    })
    res = client.get(f"{ACCOUNT}/export")
    assert res.status_code == 200 and "attachment" in res.headers["content-disposition"]
    data = res.json()
    assert data["account"]["email"] == "a@example.com" and data["account"]["accepted_terms_version"] is None
    assert data["runner_profile"]["medical_notes"] == "Asthma" and data["runner_profile"]["phone"] == "+254712345678"
    assert data["registrations"][0]["status"] == "cancelled" and data["registrations"][0]["entry_fee_kes"] == 500
    assert data["payments"][0]["amount_kes"] == 500 and data["payments"][0]["mpesa_receipt"].startswith("QGR")
    assert data["refunds"][0]["status"] == "requested"
    assert data["support_messages"][0]["message"] == "Where is my refund please?"
    assert {"channel", "to_address", "subject", "status"} <= set(data["messages_sent_to_you"][0])
    for secret in ("hashed_password", "token_hash", "raw_callback", "admin_note", "password_hash"):
        assert secret not in res.text
    assert notes(db, "data_exported")


def test_the_export_needs_a_login_and_is_limited_to_three_a_day(client):
    assert TestClient(app).get(f"{ACCOUNT}/export").status_code == 401
    signup(client, "a@example.com")
    for _ in range(3):
        assert client.get(f"{ACCOUNT}/export").status_code == 200
    res = client.get(f"{ACCOUNT}/export")
    assert res.status_code == 429 and code(res) == "rate_limited"


def test_a_name_can_be_changed(client):
    signup(client, "a@example.com", profile=False)
    res = client.patch(f"{ACCOUNT}/name", json={"full_name": "  Wanjiku W. Kamau  "})
    assert res.status_code == 200 and res.json()["full_name"] == "Wanjiku W. Kamau"
    assert client.get("/api/v1/auth/me").json()["full_name"] == "Wanjiku W. Kamau"
    assert client.patch(f"{ACCOUNT}/name", json={"full_name": "A"}).status_code == 422
    assert TestClient(app).patch(f"{ACCOUNT}/name", json={"full_name": "Someone"}).status_code == 401


def test_deletion_is_blocked_by_upcoming_events_and_open_money(client, make_event, mpesa, db):
    admin = make_admin(db)
    reg = paid_registration(client, make_event, db, mpesa)
    check = client.get(f"{ACCOUNT}/deletion-check").json()
    assert check["can_delete"] is False and {b["code"] for b in check["blockers"]} == {"upcoming_registrations"}
    res = client.post(f"{ACCOUNT}/delete-request")
    assert res.status_code == 409 and code(res) == "deletion_blocked"

    client.delete(f"/api/v1/registrations/{reg['id']}")          # a refund is now owed to this runner
    check = client.get(f"{ACCOUNT}/deletion-check").json()
    assert {b["code"] for b in check["blockers"]} == {"money_open"}

    refund = db.scalars(select(Refund)).first()
    assert admin.post(f"{A}/refunds/{refund.id}/paid", json={"mpesa_reference": "ABC1234567"}).status_code == 200
    assert client.get(f"{ACCOUNT}/deletion-check").json() == {"can_delete": True, "blockers": []}


def test_organizers_and_admins_cannot_delete_themselves(client, db):
    signup(client, "org@example.com")
    promote(db, "org@example.com", Role.organizer)
    check = client.get(f"{ACCOUNT}/deletion-check").json()
    assert check["can_delete"] is False and check["blockers"][0]["code"] == "role"
    assert client.post(f"{ACCOUNT}/delete-request").status_code == 409


def test_deletion_needs_the_emailed_link_and_a_login(client, db):
    signup(client, "a@example.com")
    assert client.post(f"{ACCOUNT}/delete-request").status_code == 202
    token = token_from(notes(db, "deletion_request")[-1])

    assert TestClient(app).post(f"{ACCOUNT}/delete-confirm", json={"token": token}).status_code == 401
    other = TestClient(app)
    signup(other, "b@example.com")
    res = other.post(f"{ACCOUNT}/delete-confirm", json={"token": token})        # someone else's link
    assert res.status_code == 400 and code(res) == "invalid_token"
    assert client.post(f"{ACCOUNT}/delete-confirm", json={"token": "nonsense-token-123"}).status_code == 400

    row = db.scalars(select(AuthToken).where(AuthToken.purpose == TokenPurpose.account_delete)).first()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert client.post(f"{ACCOUNT}/delete-confirm", json={"token": token}).status_code == 400
    assert client.get("/api/v1/auth/me").status_code == 200                       # nothing was deleted


def test_deletion_requests_are_limited(client):
    signup(client, "a@example.com", profile=False)
    for _ in range(3):
        assert client.post(f"{ACCOUNT}/delete-request").status_code == 202
    res = client.post(f"{ACCOUNT}/delete-request")
    assert res.status_code == 429 and code(res) == "rate_limited"


def test_deleting_anonymizes_the_account_but_keeps_the_money_trail(client, make_event, mpesa, db):
    make_admin(db)
    paid_registration(client, make_event, db, mpesa)
    uid = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    db.scalars(select(Event)).first().event_date = today_ke() - timedelta(days=1)       # the race has been run
    db.commit()
    client.post("/api/v1/support", json={
        "name": "Wanjiku", "email": "a@example.com", "topic": "other", "message": "A question about my results.",
    })
    assert notes(db, "support_alert")

    delete_account(client, db)

    user = db.get(User, uid)
    assert user.email.startswith("deleted-") and user.email.endswith("@deleted.invalid")
    assert user.full_name == "Deleted user" and user.is_active is False and user.deleted_at is not None
    assert db.scalars(select(RunnerProfile)).first() is None
    assert db.scalars(select(SupportMessage)).first() is None
    assert notes(db, "support_alert") == []                                    # the admins' copy goes too
    assert [n for n in db.scalars(select(Notification)) if n.user_id == uid] == []

    payment = db.scalars(select(Payment)).first()
    assert int(payment.amount) == 500 and payment.mpesa_receipt.startswith("QGR") and payment.raw_callback is None
    assert "*" in payment.phone and payment.phone != "+254712345678"
    assert db.scalars(select(Registration)).first().user_id == uid
    assert db.scalars(select(AuditLog).where(AuditLog.action == "account.deleted")).first() is not None

    farewell = notes(db, "account_deleted")
    assert len(farewell) == 1 and farewell[0].to_address == "a@example.com" and farewell[0].user_id is None

    assert client.get("/api/v1/auth/me").status_code == 401
    login = TestClient(app).post("/api/v1/auth/login", json={"email": "a@example.com", "password": PASSWORD})
    assert login.status_code == 401
    again = TestClient(app).post(
        "/api/v1/auth/signup", json={"full_name": "New Start", "email": "a@example.com", "password": PASSWORD}
    )
    assert again.status_code == 201                                            # the address is free again


def test_unpaid_holds_are_released_when_an_account_is_deleted(client, make_event, db):
    event = make_event()
    event.distances[0].capacity = 1
    db.commit()
    signup(client, "a@example.com")
    register(client, event)                                                    # a held spot, nothing paid
    delete_account(client, db)

    other = TestClient(app)
    signup(other, "b@example.com")
    assert other.post(
        f"/api/v1/events/{event.id}/registrations",
        json={"distance_id": str(event.distances[0].id), "waiver_version": WAIVER_VERSION},
    ).status_code == 201                                                       # the single spot is free again