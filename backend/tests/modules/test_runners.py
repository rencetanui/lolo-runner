from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.utils.age import age_category

PROFILE = {
    "date_of_birth": "1990-05-14",
    "gender": "female",
    "phone": "0712 345 678",
    "county": "Nakuru",
    "club": "",
    "tshirt_size": "M",
    "emergency_contact_name": "Mary Kamau",
    "emergency_contact_phone": "0722000111",
    "emergency_contact_relationship": "Sister",
    "medical_notes": "",
}


def signup(client, email="runner@example.com"):
    res = client.post(
        "/api/v1/auth/signup",
        json={"full_name": "Test Runner", "email": email, "password": "correct-horse-1"},
    )
    assert res.status_code == 201


def test_profile_requires_login(client):
    assert client.get("/api/v1/runners/me").status_code == 401
    assert client.put("/api/v1/runners/me", json=PROFILE).status_code == 401


def test_no_profile_yet_returns_404(client):
    signup(client)
    assert client.get("/api/v1/runners/me").status_code == 404


def test_create_profile_normalizes_and_computes(client):
    signup(client)
    res = client.put("/api/v1/runners/me", json=PROFILE)
    assert res.status_code == 200
    body = res.json()
    assert body["phone"] == "+254712345678"
    assert body["emergency_contact_phone"] == "+254722000111"
    assert body["club"] is None and body["medical_notes"] is None   # blanks become null
    assert body["age"] >= 35
    assert body["age_category"].startswith("F")
    assert client.get("/api/v1/runners/me").status_code == 200


def test_saving_again_updates_instead_of_duplicating(client):
    signup(client)
    client.put("/api/v1/runners/me", json=PROFILE)
    res = client.put("/api/v1/runners/me", json={**PROFILE, "club": "Nakuru Harriers"})
    assert res.status_code == 200
    assert res.json()["club"] == "Nakuru Harriers"


def test_future_birth_date_rejected(client):
    signup(client)
    future = date.today().replace(year=date.today().year + 1).isoformat()
    res = client.put("/api/v1/runners/me", json={**PROFILE, "date_of_birth": future})
    assert res.status_code == 422


def test_bad_phone_rejected(client):
    signup(client)
    res = client.put("/api/v1/runners/me", json={**PROFILE, "phone": "12345678"})
    assert res.status_code == 422


def test_profiles_are_private_to_their_owner(client):
    signup(client, "a@example.com")
    client.put("/api/v1/runners/me", json=PROFILE)

    other = TestClient(app)   # separate cookie jar, same test database
    signup(other, "b@example.com")
    assert other.get("/api/v1/runners/me").status_code == 404


def test_age_categories():
    assert age_category(15, "male") == "MU18"
    assert age_category(25, "female") == "F18-34"
    assert age_category(37, "male") == "M35-39"
    assert age_category(72, "other") == "X70+"