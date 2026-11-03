import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.registrations.waiver import WAIVER_VERSION

PROFILE = {
    "date_of_birth": "1990-05-14",
    "gender": "female",
    "phone": "0712345678",
    "tshirt_size": "M",
    "emergency_contact_name": "Mary Kamau",
    "emergency_contact_phone": "0722000111",
    "emergency_contact_relationship": "Sister",
}


@pytest.fixture(autouse=True)
def callback_secret(monkeypatch):
    monkeypatch.setattr(settings, "mpesa_callback_secret", "test-secret")


def signup(c, email="a@example.com"):
    res = c.post("/api/v1/auth/signup", json={"full_name": "Test Runner", "email": email, "password": "correct-horse-1"})
    assert res.status_code == 201
    assert c.put("/api/v1/runners/me", json=PROFILE).status_code == 200


def new_registration(client, make_event):
    event = make_event()
    signup(client)
    res = client.post(
        f"/api/v1/events/{event.id}/registrations",
        json={"distance_id": str(event.distances[0].id), "waiver_version": WAIVER_VERSION},
    )
    assert res.status_code == 201
    return res.json()


def pay(c, reg_id, phone=None):
    return c.post(f"/api/v1/registrations/{reg_id}/payments", json={"phone": phone})


def payments(c, reg_id):
    return c.get(f"/api/v1/registrations/{reg_id}/payments").json()


def reg_status(c, reg_id):
    return c.get(f"/api/v1/registrations/{reg_id}").json()["status"]


def code(res):
    return res.json()["detail"]["code"]


def stk_callback(checkout_id, result_code=0, amount=500, secret="test-secret"):
    """Plays the part of Safaricom: no login, separate client."""
    stk = {
        "MerchantRequestID": "m_1",
        "CheckoutRequestID": checkout_id,
        "ResultCode": result_code,
        "ResultDesc": "The service request is processed successfully." if result_code == 0 else "Request cancelled by user.",
    }
    if result_code == 0:
        stk["CallbackMetadata"] = {"Item": [
            {"Name": "Amount", "Value": amount},
            {"Name": "MpesaReceiptNumber", "Value": "QGR7XYZ123"},
            {"Name": "TransactionDate", "Value": 20261102101500},
            {"Name": "PhoneNumber", "Value": 254712345678},
        ]}
    return TestClient(app).post(f"/api/v1/payments/callbacks/stk/{secret}", json={"Body": {"stkCallback": stk}})


def test_start_payment_sends_stk_push(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    res = pay(client, reg["id"])
    assert res.status_code == 201
    assert res.json()["status"] == "pending"
    push = mpesa.pushes[0]
    assert push["phone"] == "254712345678"
    assert push["amount"] == 500
    assert push["reference"] == f"BIB{reg['bib_number']}"


def test_can_pay_from_a_different_number(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    assert pay(client, reg["id"], phone="0722 111 222").status_code == 201
    assert mpesa.pushes[0]["phone"] == "254722111222"


def test_non_kenyan_number_rejected(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    res = pay(client, reg["id"], phone="+441234567890")
    assert res.status_code == 422 and code(res) == "kenyan_number_required"
    assert mpesa.pushes == []


def test_successful_callback_confirms_registration_once(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    res = stk_callback("ws_CO_1")
    assert res.status_code == 200 and res.json()["ResultCode"] == 0
    assert reg_status(client, reg["id"]) == "confirmed"
    assert payments(client, reg["id"])[0]["status"] == "succeeded"
    assert stk_callback("ws_CO_1").status_code == 200       # duplicate delivery is harmless
    assert len(payments(client, reg["id"])) == 1


def test_cancelled_prompt_can_be_retried(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    stk_callback("ws_CO_1", result_code=1032)
    assert payments(client, reg["id"])[0]["status"] == "failed"
    assert reg_status(client, reg["id"]) == "pending_payment"
    assert pay(client, reg["id"]).status_code == 201
    assert len(mpesa.pushes) == 2


def test_second_prompt_blocked_while_first_is_live(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    res = pay(client, reg["id"])
    assert res.status_code == 409 and code(res) == "payment_in_progress"
    assert len(mpesa.pushes) == 1


def test_missed_callback_is_recovered_by_asking_safaricom(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    pid = pay(client, reg["id"]).json()["id"]
    mpesa.query_result = {"ResultCode": "0", "ResultDesc": "The service request is processed successfully."}
    res = client.post(f"/api/v1/payments/{pid}/check")
    assert res.status_code == 200 and res.json()["status"] == "succeeded"
    assert reg_status(client, reg["id"]) == "confirmed"


def test_retry_after_missed_success_does_not_double_charge(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    mpesa.query_result = {"ResultCode": "0", "ResultDesc": "ok"}
    res = pay(client, reg["id"])
    assert res.status_code == 409 and code(res) == "already_paid"
    assert len(mpesa.pushes) == 1


def test_wrong_secret_is_rejected(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    assert stk_callback("ws_CO_1", secret="wrong").status_code == 404
    assert reg_status(client, reg["id"]) == "pending_payment"


def test_amount_mismatch_is_flagged_not_confirmed(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    assert stk_callback("ws_CO_1", amount=1).status_code == 200
    assert payments(client, reg["id"])[0]["status"] == "needs_review"
    assert reg_status(client, reg["id"]) == "pending_payment"


def test_unknown_checkout_id_is_acknowledged(client, mpesa):
    assert stk_callback("ws_CO_nope").status_code == 200


def test_cannot_use_someone_elses_registration(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    pid = pay(client, reg["id"]).json()["id"]
    other = TestClient(app)
    signup(other, "b@example.com")
    assert pay(other, reg["id"]).status_code == 404
    assert other.get(f"/api/v1/registrations/{reg['id']}/payments").status_code == 404
    assert other.post(f"/api/v1/payments/{pid}/check").status_code == 404


def test_provider_outage_fails_cleanly_and_allows_retry(client, make_event, mpesa):
    reg = new_registration(client, make_event)
    mpesa.fail_push = True
    res = pay(client, reg["id"])
    assert res.status_code == 502 and code(res) == "provider_unavailable"
    assert payments(client, reg["id"])[0]["status"] == "failed"
    mpesa.fail_push = False
    assert pay(client, reg["id"]).status_code == 201


def test_payment_after_spot_was_released_is_flagged_for_refund(client, make_event, mpesa, db):
    reg = new_registration(client, make_event)
    pay(client, reg["id"])
    row = db.scalars(select(Registration)).first()
    row.status = RegistrationStatus.cancelled
    db.commit()
    stk_callback("ws_CO_1")
    payment = db.scalars(select(Payment)).first()
    db.refresh(payment)
    assert payment.status == PaymentStatus.succeeded and payment.needs_refund is True
    assert reg_status(client, reg["id"]) == "cancelled"