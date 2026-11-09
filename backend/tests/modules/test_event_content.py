from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.modules.auth.models import Role, User
from app.modules.notifications.models import Notification
from app.modules.registrations.waiver import WAIVER_VERSION

O = "/api/v1/organizer/events"
PROFILE = {
    "date_of_birth": "1990-05-14", "gender": "female", "phone": "0712345678", "tshirt_size": "M",
    "emergency_contact_name": "Mary Kamau", "emergency_contact_phone": "0722000111",
    "emergency_contact_relationship": "Sister",
}


def signup(c, email, name="Test Runner"):
    res = c.post("/api/v1/auth/signup", json={"full_name": name, "email": email, "password": "correct-horse-1"})
    assert res.status_code == 201
    assert c.put("/api/v1/runners/me", json=PROFILE).status_code == 200


def make_admin(db, email="admin@example.com"):
    c = TestClient(app)
    signup(c, email, "Admin")
    db.scalars(select(User).where(User.email == email)).first().role = Role.admin
    db.commit()
    return c


def register(c, event, index=0):
    res = c.post(
        f"/api/v1/events/{event.id}/registrations",
        json={"distance_id": str(event.distances[index].id), "waiver_version": WAIVER_VERSION},
    )
    assert res.status_code == 201, res.text
    return res.json()


def notes(db, kind):
    return [n for n in db.scalars(select(Notification)) if n.dedupe_key.startswith(kind)]


def event_payload(**overrides):
    today = date.today()
    payload = {
        "name": "Lake Run", "event_date": (today + timedelta(days=60)).isoformat(), "location": "Nakuru",
        "registration_opens": (today - timedelta(days=1)).isoformat(),
        "registration_closes": (today + timedelta(days=50)).isoformat(),
        "distances": [
            {"name": "5K", "km": 5, "fee": 500, "capacity": 5},
            {"name": "10K", "km": 10, "fee": 800, "capacity": 5},
        ],
    }
    payload.update(overrides)
    return payload


def test_content_is_saved_and_shown_publicly(client, db):
    admin = make_admin(db)
    payload = event_payload(
        description="A scenic run around the lake.\n\nWater points every 2 km.",
        venue_details="Start at the main gate. Parking is free.",
        map_url="https://maps.app.goo.gl/abc123",
        contact_email="info@lakerun.example",
        contact_phone="0712 345 678",
    )
    payload["distances"][0]["start_time"] = "06:30"
    payload["distances"][0]["cutoff_minutes"] = 90
    created = admin.post(O, json=payload)
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["contact_phone"] == "+254712345678"
    admin.post(f"{O}/{event['id']}/publish")

    public = TestClient(app).get(f"/api/v1/events/{event['id']}").json()
    assert public["description"].startswith("A scenic run") and "\n\n" in public["description"]
    assert public["venue_details"] == "Start at the main gate. Parking is free."
    assert public["map_url"] == "https://maps.app.goo.gl/abc123"
    assert public["contact_email"] == "info@lakerun.example" and public["contact_phone"] == "+254712345678"
    assert public["banner_url"] is None
    five, ten = public["distances"]
    assert five["start_time"] == "06:30:00" and five["cutoff_minutes"] == 90
    assert ten["start_time"] is None


def test_content_can_be_cleared_without_touching_the_rest(client, db):
    admin = make_admin(db)
    event = admin.post(O, json=event_payload(description="Hello there.", venue_details="Main gate.")).json()
    url = f"{O}/{event['id']}"
    body = admin.patch(url, json={"description": None}).json()
    assert body["description"] is None and body["venue_details"] == "Main gate."
    assert admin.patch(url, json={"venue_details": "   "}).json()["venue_details"] is None     # blank means cleared
    assert admin.patch(url, json={"name": "Renamed Run"}).status_code == 200


def test_bad_content_is_rejected(client, db):
    admin = make_admin(db)
    bad = [
        ("map_url", "javascript:alert(1)"), ("map_url", "http://insecure.example/map"), ("map_url", "not a link"),
        ("contact_email", "nope"), ("contact_phone", "12345"),
        ("description", "x" * 5001), ("venue_details", "x" * 1001),
    ]
    for field, value in bad:
        res = admin.post(O, json=event_payload(**{field: value}))
        assert res.status_code == 422, f"{field}={value[:30]!r} was accepted"


def test_changing_a_start_time_tells_only_that_distances_runners(client, make_event, db):
    admin = make_admin(db)
    event = make_event()
    for d in event.distances:
        d.fee = 0
    db.commit()
    five, ten = TestClient(app), TestClient(app)
    signup(five, "five@example.com")
    signup(ten, "ten@example.com")
    register(five, event, 0)
    register(ten, event, 1)
    url = f"{O}/{event.id}/distances/{event.distances[0].id}"

    before = len(notes(db, "event_changed"))
    assert admin.patch(url, json={"start_time": "07:00"}).status_code == 200
    new = notes(db, "event_changed")
    assert len(new) == before + 2                                   # an email and an SMS
    emails = [n for n in new if n.channel.value == "email"]
    assert {n.to_address for n in emails} == {"five@example.com"}
    assert "5K start time: not set -> 07:00" in emails[0].body_text

    assert admin.patch(url, json={"start_time": "07:00"}).status_code == 200    # unchanged: says nothing
    assert len(notes(db, "event_changed")) == before + 2


def test_start_times_can_be_cleared_and_cutoffs_are_validated(client, make_event, db):
    admin = make_admin(db)
    event = make_event()
    url = f"{O}/{event.id}/distances/{event.distances[0].id}"
    assert admin.patch(url, json={"cutoff_minutes": 5}).status_code == 422
    first = admin.patch(url, json={"start_time": "06:00", "cutoff_minutes": 120}).json()["distances"][0]
    assert first["start_time"] == "06:00:00" and first["cutoff_minutes"] == 120
    cleared = admin.patch(url, json={"start_time": None}).json()["distances"][0]
    assert cleared["start_time"] is None and cleared["cutoff_minutes"] == 120