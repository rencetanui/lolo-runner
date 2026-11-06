from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.modules.auth.models import Role, User
from app.modules.notifications.models import Notification
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.refunds.models import Refund, RefundReason, RefundStatus
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.registrations.waiver import WAIVER_VERSION
from app.utils.dates import today_ke

A = "/api/v1/admin"
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


def pay(c, reg_id):
    return c.post(f"/api/v1/registrations/{reg_id}/payments", json={"phone": None})


def stk_callback(checkout_id, result_code=0, amount=500):
    stk = {"MerchantRequestID": "m_1", "CheckoutRequestID": checkout_id, "ResultCode": result_code,
           "ResultDesc": "ok" if result_code == 0 else "Request cancelled by user."}
    if result_code == 0:
        stk["CallbackMetadata"] = {"Item": [
            {"Name": "Amount", "Value": amount}, 
            {"Name": "MpesaReceiptNumber", "Value": "QGR" + checkout_id.replace("_", "").upper()},
        ]}
    return TestClient(app).post("/api/v1/payments/callbacks/stk/test-secret", json={"Body": {"stkCallback": stk}})


def code(res):
    return res.json()["detail"]["code"]


def reg_status(c, reg_id):
    return c.get(f"/api/v1/registrations/{reg_id}").json()["status"]


def make_admin(db, email="admin@example.com"):
    c = TestClient(app)
    signup(c, email, "Admin")
    db.scalars(select(User).where(User.email == email)).first().role = Role.admin
    db.commit()
    return c


def paid_registration(c, make_event, db, mpesa, *, email="a@example.com", refund_days=10, event=None):
    event = event or make_event()
    event.refunds_until = None if refund_days is None else today_ke() + timedelta(days=refund_days)
    db.commit()
    signup(c, email)
    reg = register(c, event)
    assert pay(c, reg["id"]).status_code == 201
    assert stk_callback(f"ws_CO_{len(mpesa.pushes)}").status_code == 200
    assert reg_status(c, reg["id"]) == "confirmed"
    return reg


def late_payment(c, make_event, db, mpesa, email="late@example.com"):
    """A payment that succeeds after the runner's spot was already released."""
    event = make_event()
    signup(c, email)
    reg = register(c, event)
    pay(c, reg["id"])
    row = db.scalars(select(Registration)).first()
    row.status = RegistrationStatus.cancelled
    db.commit()
    stk_callback(f"ws_CO_{len(mpesa.pushes)}")
    return db.scalars(select(Payment)).first()


def notes(db, kind):
    return [n for n in db.scalars(select(Notification)) if n.dedupe_key.startswith(kind)]


def refund_row(db):
    return db.scalars(select(Refund)).first()


def test_cancelling_a_paid_registration_inside_the_refund_window_requests_a_refund(client, make_event, mpesa, db):
    reg = paid_registration(client, make_event, db, mpesa)
    res = client.delete(f"/api/v1/registrations/{reg['id']}")
    assert res.status_code == 200 and res.json()["status"] == "cancelled"
    refund = refund_row(db)
    assert refund.status == RefundStatus.requested and refund.reason == RefundReason.runner_cancelled
    assert int(refund.amount) == 500 and refund.phone == "+254712345678"
    assert "refund of KES 500" in notes(db, "registration_cancelled")[0].body_text
    assert notes(db, "refund_requested") == []          # the cancellation email already says it


def test_cancelling_after_the_refund_deadline_requests_nothing(client, make_event, mpesa, db):
    reg = paid_registration(client, make_event, db, mpesa, refund_days=-1)
    assert client.delete(f"/api/v1/registrations/{reg['id']}").status_code == 200
    assert refund_row(db) is None
    assert "isn't refundable" in notes(db, "registration_cancelled")[0].body_text


def test_events_without_a_refund_policy_do_not_refund(client, make_event, mpesa, db):
    reg = paid_registration(client, make_event, db, mpesa, refund_days=None)
    assert client.delete(f"/api/v1/registrations/{reg['id']}").status_code == 200
    assert refund_row(db) is None
    assert "isn't refundable" in notes(db, "registration_cancelled")[0].body_text


def test_unpaid_and_free_registrations_never_create_refunds(client, make_event, mpesa, db):
    event = make_event()
    event.refunds_until = today_ke() + timedelta(days=10)
    event.distances[1].fee = 0
    db.commit()
    signup(client, "a@example.com")
    unpaid = register(client, event, 0)
    assert client.delete(f"/api/v1/registrations/{unpaid['id']}").status_code == 200
    free = register(client, event, 1)
    assert free["status"] == "confirmed"
    assert client.delete(f"/api/v1/registrations/{free['id']}").status_code == 200
    assert refund_row(db) is None
    for n in notes(db, "registration_cancelled"):
        assert "refund" not in n.body_text.lower()


def test_cancellation_preview_matches_what_will_happen(client, make_event, mpesa, db):
    event = make_event()
    reg = paid_registration(client, make_event, db, mpesa, event=event)
    url = f"/api/v1/registrations/{reg['id']}/cancellation-preview"
    body = client.get(url).json()
    assert body["paid"] is True and body["refundable"] is True and float(body["amount"]) == 500
    assert body["refunds_until"] == (today_ke() + timedelta(days=10)).isoformat()

    event.refunds_until = today_ke() - timedelta(days=1)
    db.commit()
    body = client.get(url).json()
    assert body["paid"] is True and body["refundable"] is False and body["amount"] is None

    other = TestClient(app)
    signup(other, "b@example.com")
    unpaid = register(other, event)
    body = other.get(f"/api/v1/registrations/{unpaid['id']}/cancellation-preview").json()
    assert body["paid"] is False and body["refundable"] is False
    assert other.get(url).status_code == 404            # someone else's registration


def test_a_runner_can_follow_their_refund(client, make_event, mpesa, db):
    admin = make_admin(db)
    reg = paid_registration(client, make_event, db, mpesa)
    url = f"/api/v1/registrations/{reg['id']}/refund"
    assert client.get(url).json() is None
    client.delete(f"/api/v1/registrations/{reg['id']}")
    body = client.get(url).json()
    assert body["status"] == "requested" and float(body["amount"]) == 500
    admin.post(f"{A}/refunds/{refund_row(db).id}/paid", json={"mpesa_reference": "ABC1234567"})
    body = client.get(url).json()
    assert body["status"] == "paid" and body["mpesa_reference"] == "ABC1234567"


def test_cancelling_twice_does_not_create_two_refunds(client, make_event, mpesa, db):
    reg = paid_registration(client, make_event, db, mpesa)
    client.delete(f"/api/v1/registrations/{reg['id']}")
    client.delete(f"/api/v1/registrations/{reg['id']}")
    assert len(db.scalars(select(Refund)).all()) == 1


def test_admin_marks_a_refund_paid_and_the_runner_is_told(client, make_event, mpesa, db):
    admin = make_admin(db)
    reg = paid_registration(client, make_event, db, mpesa)
    client.delete(f"/api/v1/registrations/{reg['id']}")
    refund = refund_row(db)
    url = f"{A}/refunds/{refund.id}/paid"
    res = admin.post(url, json={"mpesa_reference": "abc1234567", "note": "Sent from the Paybill."})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "paid" and body["mpesa_reference"] == "ABC1234567"
    assert body["audit"][-1]["action"] == "refund.paid" and body["audit"][-1]["actor_name"] == "Admin"
    sent = notes(db, "refund_paid")
    assert {n.channel.value for n in sent} == {"email", "sms"}
    assert any("ABC1234567" in n.body_text for n in sent)
    again = admin.post(url, json={"mpesa_reference": "ZZZ1234567"})
    assert again.status_code == 409 and code(again) == "not_requested"


def test_a_reference_can_only_be_recorded_once(client, make_event, mpesa, db):
    admin = make_admin(db)
    event = make_event()
    first = paid_registration(client, make_event, db, mpesa, event=event)
    other = TestClient(app)
    second = paid_registration(other, make_event, db, mpesa, email="b@example.com", event=event)
    client.delete(f"/api/v1/registrations/{first['id']}")
    other.delete(f"/api/v1/registrations/{second['id']}")
    ids = [r.id for r in db.scalars(select(Refund)).all()]
    assert admin.post(f"{A}/refunds/{ids[0]}/paid", json={"mpesa_reference": "SAMECODE12"}).status_code == 200
    res = admin.post(f"{A}/refunds/{ids[1]}/paid", json={"mpesa_reference": "SAMECODE12"})
    assert res.status_code == 409 and code(res) == "duplicate_reference"
    
    db.rollback()


def test_admin_rejects_a_refund_with_a_reason_the_runner_can_read(client, make_event, mpesa, db):
    admin = make_admin(db)
    reg = paid_registration(client, make_event, db, mpesa)
    client.delete(f"/api/v1/registrations/{reg['id']}")
    url = f"{A}/refunds/{refund_row(db).id}/reject"
    assert admin.post(url, json={"note": "no"}).status_code == 422
    res = admin.post(url, json={"note": "The refund window had closed."})
    assert res.status_code == 200 and res.json()["status"] == "rejected"
    body = client.get(f"/api/v1/registrations/{reg['id']}/refund").json()
    assert body["status"] == "rejected" and body["message"] == "The refund window had closed."
    assert notes(db, "refund_rejected")


def test_admin_can_refund_a_late_payment_and_it_leaves_the_attention_list(client, make_event, mpesa, db):
    admin = make_admin(db)
    payment = late_payment(client, make_event, db, mpesa)
    assert payment.needs_refund is True
    assert admin.get(f"{A}/summary").json()["needs_refund"] == 1
    res = admin.post(f"{A}/payments/{payment.id}/refund", json={"note": "Paid after the spot was released."})
    assert res.status_code == 201 and res.json()["reason"] == "late_payment"
    summary = admin.get(f"{A}/summary").json()
    assert summary["needs_refund"] == 0 and summary["refunds_requested"] == 1
    assert notes(db, "refund_requested")                # an admin-started refund does email the runner


def test_rejecting_a_late_payment_refund_puts_the_payment_back_in_the_queue(client, make_event, mpesa, db):
    admin = make_admin(db)
    payment = late_payment(client, make_event, db, mpesa)
    created = admin.post(f"{A}/payments/{payment.id}/refund", json={"note": "Paid after the spot was released."}).json()
    res = admin.post(f"{A}/refunds/{created['id']}/reject", json={"note": "Created this one by mistake."})
    assert res.status_code == 200
    assert admin.get(f"{A}/summary").json()["needs_refund"] == 1


def test_only_paid_payments_can_be_refunded_and_only_once(client, make_event, mpesa, db):
    admin = make_admin(db)
    event = make_event()
    signup(client, "a@example.com")
    reg = register(client, event)
    pay(client, reg["id"])
    stk_callback(f"ws_CO_{len(mpesa.pushes)}", result_code=1032)
    failed = db.scalars(select(Payment)).first()
    res = admin.post(f"{A}/payments/{failed.id}/refund", json={"note": "Trying to refund a failed one."})
    assert res.status_code == 409 and code(res) == "payment_not_paid"

    other = TestClient(app)
    paid_registration(other, make_event, db, mpesa, email="b@example.com", event=event)
    paid = db.scalars(select(Payment).where(Payment.status == PaymentStatus.succeeded)).first()
    assert admin.post(f"{A}/payments/{paid.id}/refund", json={"note": "Goodwill refund for this runner."}).status_code == 201
    again = admin.post(f"{A}/payments/{paid.id}/refund", json={"note": "Trying to refund it twice."})
    assert again.status_code == 409 and code(again) == "already_refunding"


def test_refund_tools_are_admin_only(client, make_event, mpesa, db):
    reg = paid_registration(client, make_event, db, mpesa)
    client.delete(f"/api/v1/registrations/{reg['id']}")
    rid = refund_row(db).id
    assert TestClient(app).get(f"{A}/refunds").status_code == 401
    for path in ("/refunds", f"/refunds/{rid}"):
        assert client.get(f"{A}{path}").status_code == 403
    assert client.post(f"{A}/refunds/{rid}/paid", json={"mpesa_reference": "ABC1234567"}).status_code == 403
    other = TestClient(app)
    signup(other, "b@example.com")
    assert other.get(f"/api/v1/registrations/{reg['id']}/refund").status_code == 404


def test_the_admin_queue_lists_filters_and_counts_requested_refunds(client, make_event, mpesa, db):
    admin = make_admin(db)
    event = make_event()
    first = paid_registration(client, make_event, db, mpesa, event=event)
    other = TestClient(app)
    second = paid_registration(other, make_event, db, mpesa, email="b@example.com", event=event)
    client.delete(f"/api/v1/registrations/{first['id']}")
    other.delete(f"/api/v1/registrations/{second['id']}")

    queue = admin.get(f"{A}/refunds?status=requested").json()
    assert queue["total"] == 2
    assert queue["items"][0]["user"]["email"] == "a@example.com"        # oldest first
    assert admin.get(f"{A}/refunds?status=paid").json()["total"] == 0
    assert admin.get(f"{A}/refunds?q=b@example.com").json()["total"] == 1
    assert admin.get(f"{A}/summary").json()["refunds_requested"] == 2