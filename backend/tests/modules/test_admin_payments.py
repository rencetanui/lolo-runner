import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.main import app
from app.modules.auth.models import Role, User
from app.modules.notifications.models import Notification
from app.modules.payments.models import Payment
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


def register(c, event):
    res = c.post(
        f"/api/v1/events/{event.id}/registrations",
        json={"distance_id": str(event.distances[0].id), "waiver_version": WAIVER_VERSION},
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
            {"Name": "Amount", "Value": amount}, {"Name": "MpesaReceiptNumber", "Value": "QGR7XYZ123"},
        ]}
    return TestClient(app).post("/api/v1/payments/callbacks/stk/test-secret", json={"Body": {"stkCallback": stk}})


def code(res):
    return res.json()["detail"]["code"]


def reg_status(c, reg_id):
    return c.get(f"/api/v1/registrations/{reg_id}").json()["status"]


def promote(db, email, role):
    db.scalars(select(User).where(User.email == email)).first().role = role
    db.commit()


def payment_id(db, checkout_id):
    return str(db.scalars(select(Payment).where(Payment.checkout_request_id == checkout_id)).first().id)


@pytest.fixture
def admin(client, db):
    c = TestClient(app)
    signup(c, "admin@example.com", "Admin")
    promote(db, "admin@example.com", Role.admin)
    return c


@pytest.fixture
def scenario(client, make_event, mpesa, db, admin):
    """u1: wrong amount (needs review). u2: cancelled (failed). u3: still pending after 30 minutes."""
    event = make_event()
    u1, u2, u3 = TestClient(app), TestClient(app), TestClient(app)
    signup(u1, "u1@example.com", '=HYPERLINK("http://x")')
    signup(u2, "u2@example.com")
    signup(u3, "u3@example.com")
    r1, r2, r3 = register(u1, event), register(u2, event), register(u3, event)
    pay(u1, r1["id"]); stk_callback("ws_CO_1", amount=1)
    pay(u2, r2["id"]); stk_callback("ws_CO_2", result_code=1032)
    pay(u3, r3["id"])
    old = db.scalars(select(Payment).where(Payment.checkout_request_id == "ws_CO_3")).first()
    old.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    db.commit()
    return {"u1": u1, "u2": u2, "u3": u3, "r1": r1, "r2": r2, "r3": r3}


def test_only_admins_can_use_the_admin_api(client, db, admin):
    assert TestClient(app).get(f"{A}/summary").status_code == 401
    signup(client, "runner@example.com")
    for path in ("/summary", "/payments", f"/payments.csv?start={today_ke()}&end={today_ke()}"):
        assert client.get(f"{A}{path}").status_code == 403
    promote(db, "runner@example.com", Role.organizer)
    assert client.get(f"{A}/summary").status_code == 403
    assert admin.get(f"{A}/summary").status_code == 200


def test_summary_counts_what_needs_attention(scenario, admin):
    assert admin.get(f"{A}/summary").json() == {
        "needs_review": 1, "needs_refund": 0, "stuck_pending": 1, "failed_24h": 1, "refunds_requested": 0,
    }


def test_list_filters_search_and_pages(scenario, admin):
    assert admin.get(f"{A}/payments").json()["total"] == 3
    assert admin.get(f"{A}/payments?status=failed").json()["total"] == 1
    assert admin.get(f"{A}/payments?attention=true").json()["total"] == 2
    found = admin.get(f"{A}/payments?q=u2@example.com").json()
    assert found["total"] == 1 and found["items"][0]["user"]["email"] == "u2@example.com"
    first = admin.get(f"{A}/payments?page_size=2").json()
    assert len(first["items"]) == 2 and first["total"] == 3
    assert len(admin.get(f"{A}/payments?page_size=2&page=2").json()["items"]) == 1


def test_detail_shows_raw_callback_and_audit_trail(scenario, admin, db):
    detail = admin.get(f"{A}/payments/{payment_id(db, 'ws_CO_1')}").json()
    assert detail["status"] == "needs_review"
    assert detail["raw_callback"]["Body"]["stkCallback"]["CheckoutRequestID"] == "ws_CO_1"
    assert detail["audit"][0]["action"] == "payment.flagged" and detail["audit"][0]["actor_name"] is None


def test_confirming_a_reviewed_payment_confirms_the_registration(scenario, admin, db):
    pid = payment_id(db, "ws_CO_1")
    res = admin.post(f"{A}/payments/{pid}/resolve", json={
        "action": "confirm", "note": "Checked the statement: KES 500 arrived.", "mpesa_receipt": "QGR9ABC999",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "succeeded" and body["mpesa_receipt"] == "QGR9ABC999"
    assert body["audit"][-1]["action"] == "payment.confirmed" and body["audit"][-1]["actor_name"] == "Admin"
    assert reg_status(scenario["u1"], scenario["r1"]["id"]) == "confirmed"
    assert any(n.dedupe_key.startswith("registration_confirmed") for n in db.scalars(select(Notification)))


def test_dismissing_a_reviewed_payment_marks_it_failed(scenario, admin, db):
    pid = payment_id(db, "ws_CO_1")
    res = admin.post(f"{A}/payments/{pid}/resolve", json={
        "action": "dismiss", "note": "No money arrived according to the statement.",
    })
    assert res.status_code == 200 and res.json()["status"] == "failed"
    assert reg_status(scenario["u1"], scenario["r1"]["id"]) == "pending_payment"


def test_resolving_needs_a_note_and_a_payment_in_review(scenario, admin, db):
    review, failed = payment_id(db, "ws_CO_1"), payment_id(db, "ws_CO_2")
    assert admin.post(f"{A}/payments/{review}/resolve", json={"action": "confirm", "note": "ok"}).status_code == 422
    res = admin.post(f"{A}/payments/{failed}/resolve", json={"action": "confirm", "note": "Trying to confirm a failed one."})
    assert res.status_code == 409 and code(res) == "not_in_review"


def test_admin_can_recheck_a_payment_with_a_missed_callback(scenario, admin, mpesa, db):
    pid = payment_id(db, "ws_CO_3")
    mpesa.query_result = {"ResultCode": "0", "ResultDesc": "ok"}
    res = admin.post(f"{A}/payments/{pid}/check")
    assert res.status_code == 200 and res.json()["status"] == "succeeded"
    assert reg_status(scenario["u3"], scenario["r3"]["id"]) == "confirmed"


def test_csv_export_respects_the_date_range_and_neutralises_formulas(scenario, admin):
    today = today_ke().isoformat()
    res = admin.get(f"{A}/payments.csv?start={today}&end={today}")
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    assert "u2@example.com" in res.text and "'=HYPERLINK" in res.text
    old = admin.get(f"{A}/payments.csv?start=2020-01-01&end=2020-01-02")
    assert len(old.text.strip().splitlines()) == 1                  # the header row only