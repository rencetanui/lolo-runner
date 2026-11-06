from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.modules.auth.models import Role, User
from app.modules.notifications.models import Notification
from app.modules.payments import service as payments
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.registrations.waiver import WAIVER_VERSION

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


def register(c, event, index=0):
    res = c.post(
        f"/api/v1/events/{event.id}/registrations",
        json={"distance_id": str(event.distances[index].id), "waiver_version": WAIVER_VERSION},
    )
    assert res.status_code == 201, res.text
    return res.json()


def new_registration(client, make_event, email="a@example.com"):
    event = make_event()
    signup(client, email)
    return register(client, event)


def pay(c, reg_id, phone=None):
    return c.post(f"/api/v1/registrations/{reg_id}/payments", json={"phone": phone})


def reg_status(c, reg_id):
    return c.get(f"/api/v1/registrations/{reg_id}").json()["status"]


def code(res):
    return res.json()["detail"]["code"]


def stk_callback(checkout_id, result_code=0, amount=500):
    """Plays the part of Safaricom: no login, separate client."""
    stk = {
        "MerchantRequestID": "m_1", "CheckoutRequestID": checkout_id, "ResultCode": result_code,
        "ResultDesc": "The service request is processed successfully." if result_code == 0 else "Request cancelled by user.",
    }
    if result_code == 0:
        stk["CallbackMetadata"] = {"Item": [
            {"Name": "Amount", "Value": amount},
            {"Name": "MpesaReceiptNumber", "Value": "QGR7XYZ123"},
            {"Name": "PhoneNumber", "Value": 254712345678},
        ]}
    return TestClient(app).post("/api/v1/payments/callbacks/stk/test-secret", json={"Body": {"stkCallback": stk}})


def make_admin(db, email="admin@example.com"):
    c = TestClient(app)
    signup(c, email, "Admin")
    db.scalars(select(User).where(User.email == email)).first().role = Role.admin
    db.commit()
    return c


def payment_row(db):
    return db.scalars(select(Payment).order_by(Payment.created_at)).first()


def alerts(db):
    return [n for n in db.scalars(select(Notification)) if n.dedupe_key.startswith("payment_alert")]


def test_a_user_can_start_five_prompts_an_hour(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    for i in range(1, 6):
        assert pay(client, reg["id"]).status_code == 201
        stk_callback(f"ws_CO_{i}", result_code=1032)       # cancelled, so the next prompt is allowed
    res = pay(client, reg["id"])
    assert res.status_code == 429 and code(res) == "rate_limited"
    assert len(mpesa.pushes) == 5


def test_prompts_to_someone_elses_number_are_capped_across_all_users(client, make_event, mpesa):
    event = make_event()
    runners = []
    for i in range(4):
        c = TestClient(app)
        signup(c, f"u{i}@example.com")
        runners.append((c, register(c, event)))
    victim = "0708374149"
    for c, reg in runners[:3]:
        assert pay(c, reg["id"], phone=victim).status_code == 201
    c, reg = runners[3]
    assert pay(c, reg["id"], phone=victim).status_code == 429
    assert pay(c, reg["id"], phone="0722111222").status_code == 201      # a different number is still fine


def test_a_user_can_try_only_three_other_numbers_a_day(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    for i, number in enumerate(["0708374149", "0708374150", "0708374151"], start=1):
        assert pay(client, reg["id"], phone=number).status_code == 201
        stk_callback(f"ws_CO_{i}", result_code=1032)
    assert pay(client, reg["id"], phone="0708374152").status_code == 429
    assert pay(client, reg["id"]).status_code == 201                      # their own number is unaffected


def test_verification_confirms_when_mpesa_agrees(client, make_event, mpesa, db, monkeypatch):
    monkeypatch.setattr(settings, "mpesa_verify_callbacks", True)
    mpesa.query_result = {"ResultCode": "0", "ResultDesc": "ok"}
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    assert stk_callback("ws_CO_1").status_code == 200
    assert reg_status(client, reg["id"]) == "confirmed"
    assert payment_row(db).mpesa_receipt == "QGR7XYZ123"


def test_a_success_that_cannot_be_verified_yet_waits_and_is_settled_later(client, make_event, mpesa, db, monkeypatch):
    monkeypatch.setattr(settings, "mpesa_verify_callbacks", True)       # mpesa.query_result is None: "still processing"
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    assert stk_callback("ws_CO_1").status_code == 200
    p = payment_row(db)
    assert p.status == PaymentStatus.pending and "Waiting" in p.result_desc
    assert reg_status(client, reg["id"]) == "pending_payment"

    p.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()
    mpesa.query_result = {"ResultCode": "0", "ResultDesc": "ok"}
    assert payments.reconcile_pending(db, mpesa) == {"abandoned": 0, "settled": 1}
    assert reg_status(client, reg["id"]) == "confirmed"
    assert payment_row(db).mpesa_receipt == "QGR7XYZ123"                # kept from the callback


def test_a_callback_that_mpesa_contradicts_is_flagged_for_review(client, make_event, mpesa, db, monkeypatch):
    monkeypatch.setattr(settings, "mpesa_verify_callbacks", True)
    mpesa.query_result = {"ResultCode": "1032", "ResultDesc": "cancelled"}
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    assert stk_callback("ws_CO_1").status_code == 200
    p = payment_row(db)
    db.refresh(p)
    assert p.status == PaymentStatus.needs_review
    assert reg_status(client, reg["id"]) == "pending_payment"


def test_a_deferred_success_that_mpesa_later_denies_is_flagged(client, make_event, mpesa, db, monkeypatch):
    monkeypatch.setattr(settings, "mpesa_verify_callbacks", True)
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    stk_callback("ws_CO_1")                                             # can't be verified yet
    p = payment_row(db)
    p.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()
    mpesa.query_result = {"ResultCode": "1032", "ResultDesc": "cancelled"}
    payments.reconcile_pending(db, mpesa)
    db.refresh(p)
    assert p.status == PaymentStatus.needs_review
    assert reg_status(client, reg["id"]) == "pending_payment"


def test_callback_ip_allowlist(client, make_event, mpesa, db, monkeypatch):
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    monkeypatch.setattr(settings, "mpesa_callback_ips", "203.0.113.7")
    assert stk_callback("ws_CO_1").status_code == 403
    assert reg_status(client, reg["id"]) == "pending_payment"
    monkeypatch.setattr(settings, "mpesa_callback_ips", "203.0.113.7, testclient")
    assert stk_callback("ws_CO_1").status_code == 200
    assert reg_status(client, reg["id"]) == "confirmed"


def test_amount_mismatch_alerts_admins(client, make_event, mpesa, db):
    make_admin(db)
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    stk_callback("ws_CO_1", amount=1)
    db.refresh(payment_row(db))
    assert payment_row(db).status == PaymentStatus.needs_review
    sent = alerts(db)
    assert len(sent) == 1 and sent[0].to_address == "admin@example.com"
    assert "needs_review" in sent[0].dedupe_key


def test_late_success_alerts_admins(client, make_event, mpesa, db):
    make_admin(db)
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    row = db.scalars(select(Registration)).first()
    row.status = RegistrationStatus.cancelled
    db.commit()
    stk_callback("ws_CO_1")
    assert payment_row(db).needs_refund is True
    sent = alerts(db)
    assert len(sent) == 1 and "needs_refund" in sent[0].dedupe_key