import re
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.modules.auth import service as auth_service
from app.modules.auth.models import User, UserIdentity
from app.modules.auth.service import AuthError
from app.modules.notifications.models import Notification

V = "/api/v1/auth"
PASSWORD = "correct-horse-1"
CREDENTIAL = "valid-google-credential-123"


@pytest.fixture
def google(monkeypatch):
    """Pretend to be Google: whatever is in `claims` is what a valid sign-in contains."""
    monkeypatch.setattr(settings, "google_client_id", "test.apps.googleusercontent.com")
    claims: dict = {}

    def fake_verify(credential):
        if credential.startswith("bad"):
            raise AuthError("invalid_google_token", "We couldn't verify your Google sign-in. Please try again.", 401)
        return dict(claims)

    monkeypatch.setattr(auth_service, "verify_google_credential", fake_verify)
    return claims


def gclaims(**overrides):
    base = {
        "iss": "https://accounts.google.com", "sub": "g-111", "email": "wanjiku@gmail.com",
        "email_verified": True, "name": "Wanjiku Kamau",
    }
    base.update(overrides)
    return base


def google_login(c, credential=CREDENTIAL):
    return c.post(f"{V}/google", json={"credential": credential})


def password_login(c, email, password=PASSWORD):
    return c.post(f"{V}/login", json={"email": email, "password": password})


def local_signup(c, email):
    res = c.post(f"{V}/signup", json={"full_name": "Local User", "email": email, "password": PASSWORD})
    assert res.status_code == 201


def user_row(db, email):
    return db.scalars(select(User).where(User.email == email)).first()


def queued(db, kind):
    return [n for n in db.scalars(select(Notification)) if n.dedupe_key.startswith(kind)]


def code(res):
    return res.json()["detail"]["code"]


def test_google_config_reflects_settings(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    assert client.get(f"{V}/google/config").json() == {"enabled": False, "client_id": None}
    monkeypatch.setattr(settings, "google_client_id", "abc.apps.googleusercontent.com")
    assert client.get(f"{V}/google/config").json() == {"enabled": True, "client_id": "abc.apps.googleusercontent.com"}


def test_first_google_sign_in_creates_a_verified_account(client, db, google):
    google.update(gclaims())
    res = google_login(client)
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "wanjiku@gmail.com" and body["full_name"] == "Wanjiku Kamau"
    assert body["role"] == "runner" and body["email_verified"] is True and body["has_password"] is False
    assert client.get(f"{V}/me").status_code == 200
    assert db.scalars(select(UserIdentity)).first().provider_user_id == "g-111"


def test_signing_in_again_finds_the_same_account_even_if_the_email_changed(client, db, google):
    google.update(gclaims())
    first = google_login(client).json()
    google.update(gclaims(email="renamed@gmail.com"))
    second = google_login(TestClient(app)).json()
    assert second["id"] == first["id"] and second["email"] == "wanjiku@gmail.com"
    assert len(db.scalars(select(User)).all()) == 1


def test_google_links_to_a_verified_account_without_touching_its_password(client, db, google):
    local_signup(client, "wanjiku@gmail.com")
    user_row(db, "wanjiku@gmail.com").email_verified_at = datetime.now(timezone.utc)
    db.commit()
    google.update(gclaims())
    res = google_login(TestClient(app))
    assert res.status_code == 200 and res.json()["has_password"] is True
    assert password_login(TestClient(app), "wanjiku@gmail.com").status_code == 200
    assert len(queued(db, "google_linked")) == 1


def test_google_takes_over_an_unverified_account_and_locks_out_the_old_password(client, db, google):
    local_signup(client, "wanjiku@gmail.com")          # signed up, but never proved it owns the address
    google.update(gclaims())
    res = google_login(TestClient(app))
    assert res.status_code == 200
    assert res.json()["email_verified"] is True and res.json()["has_password"] is False
    assert client.get(f"{V}/me").status_code == 401                        # the old session is gone
    assert password_login(TestClient(app), "wanjiku@gmail.com").status_code == 401


def test_workspace_domains_count_as_verified(client, google):
    google.update(gclaims(email="boss@company.co.ke", hd="company.co.ke"))
    assert google_login(client).json()["email_verified"] is True


def test_other_email_providers_cannot_be_linked_to_an_existing_account(client, db, google):
    local_signup(client, "someone@outlook.com")
    google.update(gclaims(email="someone@outlook.com"))
    res = google_login(TestClient(app))
    assert res.status_code == 409 and code(res) == "account_exists"
    assert db.scalars(select(UserIdentity)).first() is None


def test_other_email_providers_get_an_unverified_account_and_a_verification_email(client, db, google, monkeypatch):
    monkeypatch.setattr(settings, "require_email_verification", True)
    google.update(gclaims(email="newbie@outlook.com"))
    res = google_login(client)
    assert res.status_code == 200 and res.json()["email_verified"] is False
    assert [n.to_address for n in queued(db, "email_verify")] == ["newbie@outlook.com"]


def test_unverified_google_emails_are_rejected(client, google):
    google.update(gclaims(email_verified=False))
    res = google_login(client)
    assert res.status_code == 400 and code(res) == "google_email_unverified"


def test_bad_tokens_are_rejected(client, google):
    res = google_login(client, credential="bad-credential-1234567")
    assert res.status_code == 401 and code(res) == "invalid_google_token"
    assert client.get(f"{V}/me").status_code == 401


def test_google_sign_in_is_off_until_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    res = google_login(client)
    assert res.status_code == 503 and code(res) == "google_not_configured"


def test_disabled_accounts_cannot_sign_in_with_google(client, db, google):
    google.update(gclaims())
    google_login(client)
    user_row(db, "wanjiku@gmail.com").is_active = False
    db.commit()
    res = google_login(TestClient(app))
    assert res.status_code == 403 and code(res) == "account_disabled"


def test_google_only_accounts_can_set_a_password_with_the_reset_flow(client, db, google):
    google.update(gclaims())
    google_login(client)
    anon = TestClient(app)
    assert password_login(anon, "wanjiku@gmail.com").status_code == 401        # no password exists yet
    anon.post(f"{V}/forgot-password", json={"email": "wanjiku@gmail.com"})
    token = re.search(r"token=([\w-]+)", queued(db, "password_reset")[-1].body_text).group(1)
    res = anon.post(f"{V}/reset-password", json={"token": token, "new_password": "battery-staple-9"})
    assert res.status_code == 200
    ok = password_login(TestClient(app), "wanjiku@gmail.com", "battery-staple-9")
    assert ok.status_code == 200 and ok.json()["has_password"] is True