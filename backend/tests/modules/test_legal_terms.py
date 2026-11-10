from sqlalchemy import select

from app.core.config import settings
from app.modules.auth import service as auth_service
from app.modules.auth.models import User
from app.modules.legal.versions import LEGAL_VERSION
from app.modules.registrations.waiver import WAIVER_VERSION

V = "/api/v1/auth"
PASSWORD = "correct-horse-1"
PROFILE = {
    "date_of_birth": "1990-05-14", "gender": "female", "phone": "0712345678", "tshirt_size": "M",
    "emergency_contact_name": "Mary Kamau", "emergency_contact_phone": "0722000111",
    "emergency_contact_relationship": "Sister",
}


def code(res):
    return res.json()["detail"]["code"]


def test_signup_requires_acceptance_and_records_it(client, db, monkeypatch):
    monkeypatch.setattr(settings, "require_terms_acceptance", True)
    body = {"full_name": "Wanjiku Kamau", "email": "a@example.com", "password": PASSWORD}
    res = client.post(f"{V}/signup", json=body)
    assert res.status_code == 422 and code(res) == "terms_required"
    assert db.scalars(select(User)).first() is None

    ok = client.post(f"{V}/signup", json={**body, "accept_terms": True})
    assert ok.status_code == 201 and ok.json()["needs_terms"] is False
    user = db.scalars(select(User)).first()
    assert user.legal_version == LEGAL_VERSION and user.legal_accepted_at is not None


def test_users_on_an_old_version_must_accept_again_before_registering(client, make_event, db, monkeypatch):
    monkeypatch.setattr(settings, "require_terms_acceptance", True)
    event = make_event()
    client.post(f"{V}/signup", json={
        "full_name": "Wanjiku Kamau", "email": "a@example.com", "password": PASSWORD, "accept_terms": True,
    })
    assert client.put("/api/v1/runners/me", json=PROFILE).status_code == 200
    db.scalars(select(User)).first().legal_version = "an-older-version"
    db.commit()
    assert client.get(f"{V}/me").json()["needs_terms"] is True

    url = f"/api/v1/events/{event.id}/registrations"
    body = {"distance_id": str(event.distances[0].id), "waiver_version": WAIVER_VERSION}
    res = client.post(url, json=body)
    assert res.status_code == 403 and code(res) == "terms_not_accepted"

    accepted = client.post(f"{V}/accept-terms")
    assert accepted.status_code == 200 and accepted.json()["needs_terms"] is False
    assert client.post(url, json=body).status_code == 201


def test_google_sign_up_needs_acceptance_too(client, db, monkeypatch):
    monkeypatch.setattr(settings, "require_terms_acceptance", True)
    monkeypatch.setattr(settings, "google_client_id", "test.apps.googleusercontent.com")
    monkeypatch.setattr(auth_service, "verify_google_credential", lambda credential: {
        "iss": "https://accounts.google.com", "sub": "g-1", "email": "new@gmail.com",
        "email_verified": True, "name": "New Person",
    })
    credential = "valid-google-credential-123"
    res = client.post(f"{V}/google", json={"credential": credential})
    assert res.status_code == 422 and code(res) == "terms_required"
    assert db.scalars(select(User)).first() is None

    ok = client.post(f"{V}/google", json={"credential": credential, "accept_terms": True})
    assert ok.status_code == 200
    assert db.scalars(select(User)).first().legal_version == LEGAL_VERSION


def test_the_current_legal_version_is_public(client):
    assert client.get("/api/v1/legal/version").json() == {"version": LEGAL_VERSION}