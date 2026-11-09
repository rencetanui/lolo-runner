from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.modules.auth.models import Role, User
from app.modules.registrations.waiver import WAIVER_VERSION

BASE = "/api/v1/organizer/events"

PROFILE = {
    "date_of_birth": "1990-05-14",
    "gender": "female",
    "phone": "0712345678",
    "tshirt_size": "M",
    "emergency_contact_name": "Mary Kamau",
    "emergency_contact_phone": "0722000111",
    "emergency_contact_relationship": "Sister",
}


def event_payload(**overrides):
    today = date.today()
    payload = {
        "name": "Nakuru Sunrise Run",
        "event_date": (today + timedelta(days=60)).isoformat(),
        "location": "Nakuru",
        "registration_opens": (today - timedelta(days=1)).isoformat(),
        "registration_closes": (today + timedelta(days=50)).isoformat(),
        "distances": [
            {"name": "5K", "km": 5, "fee": 500, "capacity": 5, "min_age": 12},
            {"name": "10K", "km": 10, "fee": 800, "capacity": 5, "min_age": 14},
        ],
    }
    payload.update(overrides)
    return payload


def code(res):
    return res.json()["detail"]["code"]


def signup(c, email, name="Test User"):
    res = c.post("/api/v1/auth/signup", json={"full_name": name, "email": email, "password": "correct-horse-1"})
    assert res.status_code == 201


def promote(db, email, role):
    user = db.scalars(select(User).where(User.email == email)).first()
    user.role = role
    db.commit()


@pytest.fixture
def org(client, db):
    signup(client, "org@example.com", "Olivia Organizer")
    promote(db, "org@example.com", Role.organizer)
    return client


def new_runner(email, name="Test Runner"):
    c = TestClient(app)
    signup(c, email, name)
    assert c.put("/api/v1/runners/me", json=PROFILE).status_code == 200
    return c


def create_event(c, **overrides):
    res = c.post(BASE, json=event_payload(**overrides))
    assert res.status_code == 201, res.text
    return res.json()


def publish(c, event):
    res = c.post(f"{BASE}/{event['id']}/publish")
    assert res.status_code == 200, res.text
    return res.json()


def sign_up_for(c, event, index=0):
    return c.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"distance_id": event["distances"][index]["id"], "waiver_version": WAIVER_VERSION},
    )


def test_runners_cannot_use_organizer_endpoints(client):
    assert client.get(BASE).status_code == 401
    signup(client, "run@example.com")
    assert client.get(BASE).status_code == 403
    assert client.post(BASE, json=event_payload()).status_code == 403


def test_new_event_is_a_draft_hidden_from_the_public(org):
    event = create_event(org)
    assert event["status"] == "draft"
    public = TestClient(app)
    assert public.get("/api/v1/events").json() == []
    assert public.get(f"/api/v1/events/{event['id']}").status_code == 404
    assert public.get(f"/api/v1/events/{event['id']}/availability").status_code == 404
    assert sign_up_for(new_runner("r1@example.com"), event).status_code == 404


def test_publishing_makes_the_event_public(org):
    event = create_event(org)
    assert publish(org, event)["status"] == "published"
    public = TestClient(app)
    assert [e["name"] for e in public.get("/api/v1/events").json()] == ["Nakuru Sunrise Run"]
    assert sign_up_for(new_runner("r1@example.com"), event).status_code == 201


def test_cannot_publish_without_distances(org):
    event = create_event(org, distances=[])
    res = org.post(f"{BASE}/{event['id']}/publish")
    assert res.status_code == 422 and code(res) == "no_distances"


def test_dates_must_be_in_order(org):
    today = date.today()
    res = org.post(BASE, json=event_payload(registration_closes=(today + timedelta(days=90)).isoformat()))
    assert res.status_code == 422 and code(res) == "invalid_dates"
    res = org.post(BASE, json=event_payload(registration_opens=(today + timedelta(days=55)).isoformat()))
    assert res.status_code == 422 and code(res) == "invalid_dates"


def test_cannot_create_event_in_the_past(org):
    today = date.today()
    res = org.post(BASE, json=event_payload(
        event_date=(today - timedelta(days=1)).isoformat(),
        registration_opens=(today - timedelta(days=10)).isoformat(),
        registration_closes=(today - timedelta(days=2)).isoformat(),
    ))
    assert res.status_code == 422 and code(res) == "event_in_past"


def test_fee_must_be_whole_shillings(org):
    bad = [{"name": "5K", "km": 5, "fee": 500.5, "capacity": 5}]
    assert org.post(BASE, json=event_payload(distances=bad)).status_code == 422


def test_update_validates_dates_against_existing_values(org):
    event = create_event(org)
    url = f"{BASE}/{event['id']}"
    res = org.patch(url, json={"name": "Renamed Run"})
    assert res.status_code == 200 and res.json()["name"] == "Renamed Run"

    later = (date.today() + timedelta(days=200)).isoformat()
    res = org.patch(url, json={"registration_closes": later})    # would close after the event
    assert res.status_code == 422 and code(res) == "invalid_dates"

    much_later = (date.today() + timedelta(days=300)).isoformat()
    assert org.patch(url, json={"event_date": much_later, "registration_closes": later}).status_code == 200


def test_organizers_only_manage_their_own_events(org, db):
    event = create_event(org)

    other = TestClient(app)
    signup(other, "org2@example.com")
    promote(db, "org2@example.com", Role.organizer)
    assert other.get(f"{BASE}/{event['id']}").status_code == 404
    assert other.patch(f"{BASE}/{event['id']}", json={"name": "Hijacked"}).status_code == 404
    assert other.get(BASE).json() == []

    admin = TestClient(app)
    signup(admin, "admin@example.com")
    promote(db, "admin@example.com", Role.admin)
    assert admin.get(f"{BASE}/{event['id']}").status_code == 200
    assert len(admin.get(BASE).json()) == 1


def test_capacity_cannot_drop_below_registrations(org):
    event = publish(org, create_event(org))
    for i in range(2):
        assert sign_up_for(new_runner(f"r{i}@example.com"), event).status_code == 201
    url = f"{BASE}/{event['id']}/distances/{event['distances'][0]['id']}"
    res = org.patch(url, json={"capacity": 1})
    assert res.status_code == 409 and code(res) == "capacity_below_registrations"
    assert org.patch(url, json={"capacity": 2}).status_code == 200


def test_distance_basics_locked_once_runners_register(org):
    event = publish(org, create_event(org))
    runner = new_runner("r1@example.com")
    reg = sign_up_for(runner, event).json()
    url = f"{BASE}/{event['id']}/distances/{event['distances'][0]['id']}"

    for change in ({"name": "6K"}, {"km": 6}, {"min_age": 16}):
        res = org.patch(url, json=change)
        assert res.status_code == 409 and code(res) == "distance_locked"

    assert org.patch(url, json={"fee": 700}).status_code == 200
    # the runner who already registered keeps the price they signed up at
    assert runner.get(f"/api/v1/registrations/{reg['id']}").json()["fee_amount"] == "500.00"


def test_cannot_delete_distance_with_registrations(org):
    event = publish(org, create_event(org))
    sign_up_for(new_runner("r1@example.com"), event, 0)      # registers for the 5K
    five, ten = event["distances"]
    res = org.delete(f"{BASE}/{event['id']}/distances/{five['id']}")
    assert res.status_code == 409 and code(res) == "distance_has_registrations"
    assert org.delete(f"{BASE}/{event['id']}/distances/{ten['id']}").status_code == 200


def test_published_event_keeps_one_distance(org):
    event = create_event(org, distances=[{"name": "5K", "km": 5, "fee": 0, "capacity": 5}])
    publish(org, event)
    res = org.delete(f"{BASE}/{event['id']}/distances/{event['distances'][0]['id']}")
    assert res.status_code == 409 and code(res) == "last_distance", res.text


def test_unpublish_blocked_with_registrations(org):
    event = publish(org, create_event(org))
    sign_up_for(new_runner("r1@example.com"), event)
    res = org.post(f"{BASE}/{event['id']}/unpublish")
    assert res.status_code == 409 and code(res) == "has_registrations"


def test_unpublish_hides_the_event_again(org):
    event = publish(org, create_event(org))
    res = org.post(f"{BASE}/{event['id']}/unpublish")
    assert res.status_code == 200 and res.json()["status"] == "draft"
    assert TestClient(app).get("/api/v1/events").json() == []


def test_delete_event_rules(org):
    draft = create_event(org)
    assert org.delete(f"{BASE}/{draft['id']}").status_code == 204
    assert org.get(f"{BASE}/{draft['id']}").status_code == 404

    event = publish(org, create_event(org, name="With runners"))
    sign_up_for(new_runner("r1@example.com"), event)
    res = org.delete(f"{BASE}/{event['id']}")
    assert res.status_code == 409 and code(res) == "event_has_registrations"


def test_participants_list_and_csv(org):
    event = publish(org, create_event(org))
    sign_up_for(new_runner("r1@example.com", "Wanjiku Kamau"), event, 0)
    r2 = new_runner("r2@example.com", '=HYPERLINK("http://evil")')
    reg2 = sign_up_for(r2, event, 1).json()

    page = org.get(f"{BASE}/{event['id']}/participants").json()
    assert page["total"] == 2
    first = page["items"][0]
    assert first["full_name"] == "Wanjiku Kamau" and first["bib_number"] == 1
    assert first["distance_name"] == "5K"
    assert "medical_notes" not in first and "emergency_contact_name" not in first

    res = org.get(f"{BASE}/{event['id']}/participants.csv")
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    assert "Wanjiku Kamau" in res.text
    assert "'=HYPERLINK" in res.text            # formula injection neutralised

    r2.delete(f"/api/v1/registrations/{reg2['id']}")
    assert org.get(f"{BASE}/{event['id']}/participants").json()["total"] == 1
    assert org.get(f"{BASE}/{event['id']}/participants?include_cancelled=true").json()["total"] == 2