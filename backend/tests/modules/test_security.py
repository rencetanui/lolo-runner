import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.requests import Request

from app.core.config import settings
from app.core.rate_limit import client_ip
from app.main import app
from app.modules.auth import service as auth_service
from app.modules.auth.models import AuthToken, RateLimit, TokenPurpose
from app.modules.notifications import service as notifications
from app.modules.notifications.models import Notification, NotificationStatus
from app.modules.registrations.waiver import WAIVER_VERSION

PASSWORD = "correct-horse-1"
NEW_PASSWORD = "battery-staple-9"
PROFILE = {
    "date_of_birth": "1990-05-14", "gender": "female", "phone": "0712345678", "tshirt_size": "M",
    "emergency_contact_name": "Mary Kamau", "emergency_contact_phone": "0722000111",
    "emergency_contact_relationship": "Sister",
}
V = "/api/v1/auth"


@pytest.fixture(autouse=True)
def verification_on(monkeypatch):
    monkeypatch.setattr(settings, "require_email_verification", True)


class FakeEmail:
    def __init__(self):
        self.sent = []

    def send(self, *, to, subject, text, html=None):
        self.sent.append({"to": to, "text": text})


class FakeSms:
    def send(self, *, to, message):
        return None


def signup(c, email="a@example.com"):
    res = c.post(f"{V}/signup", json={"full_name": "Wanjiku Kamau", "email": email, "password": PASSWORD})
    assert res.status_code == 201, res.text
    return res.json()


def login(c, email="a@example.com", password=PASSWORD):
    return c.post(f"{V}/login", json={"email": email, "password": password})


def emails(db, kind):
    rows = db.scalars(select(Notification).order_by(Notification.created_at))
    return [n for n in rows if n.dedupe_key.startswith(kind)]


def latest(db, kind):
    return emails(db, kind)[-1]


def token_from(note):
    return re.search(r"token=([\w-]+)", note.body_text).group(1)


def code(res):
    return res.json()["detail"]["code"]


# ---------------------------------------------------------------- verification
def test_signup_sends_a_verification_link_and_stores_only_its_hash(client, db):
    assert signup(client)["email_verified"] is False
    note = latest(db, "email_verify")
    assert note.to_address == "a@example.com" and note.sensitive is True
    raw = token_from(note)
    stored = db.scalars(select(AuthToken)).first()
    assert stored.token_hash != raw and raw not in stored.token_hash


def test_verifying_works_once_and_a_second_click_is_harmless(client, db):
    signup(client)
    raw = token_from(latest(db, "email_verify"))
    anon = TestClient(app)
    assert anon.post(f"{V}/verify-email", json={"token": raw}).status_code == 200
    assert client.get(f"{V}/me").json()["email_verified"] is True
    assert anon.post(f"{V}/verify-email", json={"token": raw}).status_code == 200
    bad = anon.post(f"{V}/verify-email", json={"token": "nonsense-token-123"})
    assert bad.status_code == 400 and code(bad) == "invalid_token"


def test_expired_verification_link_is_rejected(client, db):
    signup(client)
    raw = token_from(latest(db, "email_verify"))
    db.scalars(select(AuthToken)).first().expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert TestClient(app).post(f"{V}/verify-email", json={"token": raw}).status_code == 400


def test_a_reset_link_cannot_be_used_to_verify_an_email(client, db):
    signup(client)
    anon = TestClient(app)
    anon.post(f"{V}/forgot-password", json={"email": "a@example.com"})
    raw = token_from(latest(db, "password_reset"))
    assert anon.post(f"{V}/verify-email", json={"token": raw}).status_code == 400


def test_registering_requires_a_verified_email(client, make_event, db):
    event = make_event()
    signup(client)
    assert client.put("/api/v1/runners/me", json=PROFILE).status_code == 200
    body = {"distance_id": str(event.distances[0].id), "waiver_version": WAIVER_VERSION}
    url = f"/api/v1/events/{event.id}/registrations"

    res = client.post(url, json=body)
    assert res.status_code == 403 and code(res) == "email_unverified"

    TestClient(app).post(f"{V}/verify-email", json={"token": token_from(latest(db, "email_verify"))})
    assert client.post(url, json=body).status_code == 201


def test_resending_replaces_the_old_link(client, db):
    signup(client)
    first = token_from(latest(db, "email_verify"))
    assert client.post(f"{V}/resend-verification").status_code == 202
    second = token_from(latest(db, "email_verify"))
    anon = TestClient(app)
    assert anon.post(f"{V}/verify-email", json={"token": first}).status_code == 400
    assert anon.post(f"{V}/verify-email", json={"token": second}).status_code == 200


def test_resending_is_limited_to_three_an_hour(client):
    signup(client)
    for _ in range(3):
        assert client.post(f"{V}/resend-verification").status_code == 202
    res = client.post(f"{V}/resend-verification")
    assert res.status_code == 429 and "Retry-After" in res.headers


# ---------------------------------------------------------------- forgot / reset
def test_forgot_password_never_reveals_whether_an_account_exists(client, db):
    signup(client)
    anon = TestClient(app)
    known = anon.post(f"{V}/forgot-password", json={"email": "a@example.com"})
    unknown = anon.post(f"{V}/forgot-password", json={"email": "ghost@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert [n.to_address for n in emails(db, "password_reset")] == ["a@example.com"]


def test_reset_emails_are_capped_per_address_but_the_latest_link_works(client, db):
    signup(client)
    anon = TestClient(app)
    for _ in range(5):
        assert anon.post(f"{V}/forgot-password", json={"email": "a@example.com"}).status_code == 202
    sent = emails(db, "password_reset")
    assert len(sent) == 3
    res = anon.post(f"{V}/reset-password", json={"token": token_from(sent[-1]), "new_password": NEW_PASSWORD})
    assert res.status_code == 200


def test_forgot_password_is_limited_per_ip(client):
    for i in range(20):
        assert client.post(f"{V}/forgot-password", json={"email": f"u{i}@example.com"}).status_code == 202
    assert client.post(f"{V}/forgot-password", json={"email": "x@example.com"}).status_code == 429


def test_reset_changes_the_password_signs_out_every_session_and_verifies_the_email(client, db):
    signup(client)
    other = TestClient(app)
    assert login(other).status_code == 200
    anon = TestClient(app)
    anon.post(f"{V}/forgot-password", json={"email": "a@example.com"})
    raw = token_from(latest(db, "password_reset"))

    assert anon.post(f"{V}/reset-password", json={"token": raw, "new_password": NEW_PASSWORD}).status_code == 200
    assert client.get(f"{V}/me").status_code == 401 and other.get(f"{V}/me").status_code == 401
    assert login(TestClient(app), password=PASSWORD).status_code == 401
    ok = login(TestClient(app), password=NEW_PASSWORD)
    assert ok.status_code == 200 and ok.json()["email_verified"] is True
    assert emails(db, "password_changed")

    again = anon.post(f"{V}/reset-password", json={"token": raw, "new_password": "another-pass-1"})
    assert again.status_code == 400 and code(again) == "invalid_token"


def test_reset_rejects_weak_passwords_and_expired_links(client, db):
    signup(client)
    anon = TestClient(app)
    anon.post(f"{V}/forgot-password", json={"email": "a@example.com"})
    raw = token_from(latest(db, "password_reset"))
    assert anon.post(f"{V}/reset-password", json={"token": raw, "new_password": "short"}).status_code == 422

    row = db.scalars(select(AuthToken).where(AuthToken.purpose == TokenPurpose.password_reset)).first()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert anon.post(f"{V}/reset-password", json={"token": raw, "new_password": NEW_PASSWORD}).status_code == 400


def test_secret_links_are_wiped_from_the_outbox_after_delivery(client, db):
    signup(client)
    raw = token_from(latest(db, "email_verify"))
    sender = FakeEmail()
    notifications.process_due(db, sender, FakeSms())
    note = latest(db, "email_verify")
    assert raw in sender.sent[0]["text"]
    assert note.status == NotificationStatus.sent
    assert note.body_text == "[redacted]" and note.body_html is None


# ---------------------------------------------------------------- login limits
def test_repeated_wrong_passwords_lock_login_for_a_while(client):
    signup(client)
    client.post(f"{V}/logout")
    anon = TestClient(app)
    for _ in range(10):
        assert login(anon, password="wrong-password-1").status_code == 401
    res = login(anon)                                  # even the right password is refused for now
    assert res.status_code == 429 and int(res.headers["Retry-After"]) > 0
    assert login(anon, email="someone-else@example.com").status_code == 401    # other accounts unaffected


def test_successful_logins_do_not_count_towards_the_limit(client):
    signup(client)
    for _ in range(12):
        assert login(TestClient(app)).status_code == 200


# ---------------------------------------------------------------- change password
def test_changing_password_keeps_this_session_and_signs_out_the_others(client, db):
    signup(client)
    other = TestClient(app)
    login(other)
    res = client.post(f"{V}/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert res.status_code == 200
    assert client.get(f"{V}/me").status_code == 200
    assert other.get(f"{V}/me").status_code == 401
    assert emails(db, "password_changed")


def test_change_password_checks_the_current_password(client):
    signup(client)
    bad = client.post(f"{V}/change-password", json={"current_password": "wrong-password-1", "new_password": NEW_PASSWORD})
    assert bad.status_code == 400 and code(bad) == "incorrect_password"
    same = client.post(f"{V}/change-password", json={"current_password": PASSWORD, "new_password": PASSWORD})
    assert same.status_code == 400 and code(same) == "same_password"


def test_wrong_current_passwords_are_limited(client):
    signup(client)
    wrong = {"current_password": "wrong-password-1", "new_password": NEW_PASSWORD}
    for _ in range(5):
        assert client.post(f"{V}/change-password", json=wrong).status_code == 400
    ok = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    assert client.post(f"{V}/change-password", json=ok).status_code == 429


# ---------------------------------------------------------------- plumbing
def test_forwarded_headers_are_only_trusted_when_configured(monkeypatch):
    request = Request({
        "type": "http", "client": ("9.9.9.9", 1234),
        "headers": [(b"x-forwarded-for", b"1.1.1.1, 2.2.2.2")],
    })
    assert client_ip(request) == "9.9.9.9"
    monkeypatch.setattr(settings, "trusted_proxies", 1)
    assert client_ip(request) == "2.2.2.2"
    monkeypatch.setattr(settings, "trusted_proxies", 2)
    assert client_ip(request) == "1.1.1.1"


def test_responses_carry_security_headers(client):
    res = client.get(f"{V}/me")
    assert res.headers["Cache-Control"] == "no-store" and res.headers["X-Content-Type-Options"] == "nosniff"
    assert "no-store" not in client.get("/api/v1/events").headers.get("Cache-Control", "")


def test_expired_tokens_and_old_rate_limit_rows_are_purged(client, db):
    signup(client)
    db.scalars(select(AuthToken)).first().expires_at = datetime.now(timezone.utc) - timedelta(days=10)
    db.add(RateLimit(key="old", window_start=1, hits=3))
    db.commit()
    assert auth_service.purge_expired(db) == {"tokens": 1, "rate_limits": 1}