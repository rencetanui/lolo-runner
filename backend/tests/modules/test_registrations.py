from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.modules.registrations.models import Registration
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


def signup(c, email, with_profile=True, dob="1990-05-14"):
    res = c.post(
        "/api/v1/auth/signup",
        json={"full_name": "Test Runner", "email": email, "password": "correct-horse-1"},
    )
    assert res.status_code == 201
    if with_profile:
        res = c.put("/api/v1/runners/me", json={**PROFILE, "date_of_birth": dob})
        assert res.status_code == 200


def register(c, event, distance, **extra):
    body = {"distance_id": str(distance.id), "waiver_version": WAIVER_VERSION, **extra}
    return c.post(f"/api/v1/events/{event.id}/registrations", json=body)


def code(res):
    return res.json()["detail"]["code"]


def test_paid_distance_is_held_pending_payment(client, make_event):
    event = make_event()
    signup(client, "a@example.com")
    res = register(client, event, event.distances[0])
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "pending_payment"
    assert body["bib_number"] == 1
    assert body["fee_amount"] == "500.00"
    assert body["expires_at"] is not None
    assert body["event"]["name"] == event.name


def test_free_distance_is_confirmed_immediately(client, make_event, db):
    event = make_event()
    event.distances[0].fee = 0
    db.commit()
    signup(client, "a@example.com")
    body = register(client, event, event.distances[0]).json()
    assert body["status"] == "confirmed"
    assert body["expires_at"] is None


def test_requires_login(client, make_event):
    event = make_event()
    assert register(client, event, event.distances[0]).status_code == 401


def test_requires_runner_profile(client, make_event):
    event = make_event()
    signup(client, "a@example.com", with_profile=False)
    res = register(client, event, event.distances[0])
    assert res.status_code == 409 and code(res) == "profile_required"


def test_outdated_waiver_rejected(client, make_event):
    event = make_event()
    signup(client, "a@example.com")
    res = register(client, event, event.distances[0], waiver_version="old-version")
    assert res.status_code == 422 and code(res) == "waiver_outdated"


def test_cannot_register_twice_for_same_event(client, make_event):
    event = make_event()
    signup(client, "a@example.com")
    assert register(client, event, event.distances[0]).status_code == 201
    res = register(client, event, event.distances[1])   # even a different distance
    assert res.status_code == 409 and code(res) == "already_registered"


def test_bibs_increment_per_event(client, make_event):
    event = make_event()
    other = TestClient(app)
    signup(client, "a@example.com")
    signup(other, "b@example.com")
    assert register(client, event, event.distances[0]).json()["bib_number"] == 1
    assert register(other, event, event.distances[0]).json()["bib_number"] == 2


def test_sold_out(client, make_event, db):
    event = make_event()
    event.distances[0].capacity = 1
    db.commit()
    other = TestClient(app)
    signup(client, "a@example.com")
    signup(other, "b@example.com")
    assert register(client, event, event.distances[0]).status_code == 201
    res = register(other, event, event.distances[0])
    assert res.status_code == 409 and code(res) == "sold_out"


def test_cancelling_frees_the_spot(client, make_event, db):
    event = make_event()
    event.distances[0].capacity = 1
    db.commit()
    other = TestClient(app)
    signup(client, "a@example.com")
    signup(other, "b@example.com")
    reg_id = register(client, event, event.distances[0]).json()["id"]
    res = client.delete(f"/api/v1/registrations/{reg_id}")
    assert res.status_code == 200 and res.json()["status"] == "cancelled"
    assert register(other, event, event.distances[0]).status_code == 201


def test_expired_hold_frees_the_spot(client, make_event, db):
    event = make_event()
    event.distances[0].capacity = 1
    db.commit()
    other = TestClient(app)
    signup(client, "a@example.com")
    signup(other, "b@example.com")
    assert register(client, event, event.distances[0]).status_code == 201

    reg = db.scalars(select(Registration)).first()
    reg.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    assert register(other, event, event.distances[0]).status_code == 201


def test_minor_needs_guardian_consent(client, make_event):
    event = make_event()
    signup(client, "kid@example.com", dob=f"{date.today().year - 15}-01-01")
    res = register(client, event, event.distances[0])
    assert res.status_code == 422 and code(res) == "guardian_consent_required"
    assert register(client, event, event.distances[0], guardian_consent=True).status_code == 201


def test_below_minimum_age_rejected(client, make_event, db):
    event = make_event()
    event.distances[1].min_age = 40      # runner in the profile is ~36
    db.commit()
    signup(client, "a@example.com")
    res = register(client, event, event.distances[1])
    assert res.status_code == 409 and code(res) == "too_young"


def test_closed_registration_rejected(client, make_event):
    event = make_event(days_from_now=3)   # registration closed 2 days ago
    signup(client, "a@example.com")
    res = register(client, event, event.distances[0])
    assert res.status_code == 409 and code(res) == "registration_closed"


def test_cannot_cancel_someone_elses_registration(client, make_event):
    event = make_event()
    other = TestClient(app)
    signup(client, "a@example.com")
    signup(other, "b@example.com")
    reg_id = register(client, event, event.distances[0]).json()["id"]
    assert other.delete(f"/api/v1/registrations/{reg_id}").status_code == 404
    assert other.get(f"/api/v1/registrations/{reg_id}").status_code == 404


def test_availability_counts_active_registrations(client, make_event, db):
    event = make_event()
    event.distances[0].capacity = 5
    db.commit()
    signup(client, "a@example.com")
    register(client, event, event.distances[0])
    body = client.get(f"/api/v1/events/{event.id}/availability").json()
    five_k = next(d for d in body if d["distance_id"] == str(event.distances[0].id))
    assert five_k["spots_left"] == 4