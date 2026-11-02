SIGNUP = {"full_name": "Wanjiku Kamau", "email": "Wanjiku@Example.com", "password": "correct-horse-1"}


def test_signup_logs_user_in_and_hides_password(client):
    res = client.post("/api/v1/auth/signup", json=SIGNUP)
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "wanjiku@example.com"   # normalized
    assert body["role"] == "runner"
    assert "hashed_password" not in body and "password" not in body
    assert client.get("/api/v1/auth/me").status_code == 200


def test_duplicate_email_rejected_case_insensitively(client):
    client.post("/api/v1/auth/signup", json=SIGNUP)
    res = client.post("/api/v1/auth/signup", json={**SIGNUP, "email": "WANJIKU@example.com"})
    assert res.status_code == 409


def test_short_password_rejected(client):
    res = client.post("/api/v1/auth/signup", json={**SIGNUP, "password": "short"})
    assert res.status_code == 422


def test_login_wrong_password_and_unknown_email_look_identical(client):
    client.post("/api/v1/auth/signup", json=SIGNUP)
    client.post("/api/v1/auth/logout")
    wrong = client.post("/api/v1/auth/login", json={"email": SIGNUP["email"], "password": "nope-nope-nope"})
    unknown = client.post("/api/v1/auth/login", json={"email": "who@example.com", "password": "nope-nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_me_requires_login(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_ends_session(client):
    client.post("/api/v1/auth/signup", json=SIGNUP)
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_tampered_cookie_rejected(client):
    client.cookies.set("access_token", "not.a.real.token")
    assert client.get("/api/v1/auth/me").status_code == 401