from app.core.config import Settings, deployment_problems


def make(**over):
    base = dict(
        _env_file=None, database_url="postgresql+psycopg://u:p@db/x", secret_key="k" * 40, environment="production",
        cookie_secure=True, trusted_proxies=1, frontend_url="https://lolo.example", public_base_url="https://lolo.example",
        cors_origins=["https://lolo.example"], mpesa_callback_secret="s" * 32, mpesa_env="production",
        mpesa_consumer_key="k", mpesa_consumer_secret="s", mpesa_shortcode="123456", mpesa_passkey="p",
        email_backend="smtp", smtp_host="smtp.example.com", sms_backend="africastalking", at_env="production",
        at_api_key="k", require_email_verification=True, require_terms_acceptance=True,
    )
    base.update(over)
    return Settings(**base)


def test_development_is_never_blocked():
    assert deployment_problems(make(environment="development", secret_key="x", cookie_secure=False)) == []


def test_a_complete_production_configuration_passes():
    assert deployment_problems(make()) == []


def test_every_unsafe_setting_is_reported_exactly_once():
    cases = {
        "SECRET_KEY": dict(secret_key="short"),
        "COOKIE_SECURE": dict(cookie_secure=False),
        "TRUSTED_PROXIES": dict(trusted_proxies=0),
        "FRONTEND_URL": dict(frontend_url="http://lolo.example"),
        "PUBLIC_BASE_URL": dict(public_base_url="http://localhost:8000"),
        "CORS_ORIGINS": dict(cors_origins=["http://localhost:5173"]),
        "MPESA_CALLBACK_SECRET": dict(mpesa_callback_secret=""),
        "MPESA_ENV": dict(mpesa_env="mock"),
        "Missing M-Pesa": dict(mpesa_passkey=""),
        "EMAIL_BACKEND": dict(email_backend="console"),
        "SMS must": dict(sms_backend="console"),
        "REQUIRE_EMAIL_VERIFICATION": dict(require_email_verification=False),
        "REQUIRE_TERMS_ACCEPTANCE": dict(require_terms_acceptance=False),
    }
    for expected, change in cases.items():
        found = deployment_problems(make(**change))
        assert len(found) == 1 and expected in found[0], (expected, found)


def test_staging_may_use_the_sandbox_but_not_skip_the_security_basics():
    relaxed = make(environment="staging", mpesa_env="sandbox", email_backend="console", sms_backend="console")
    assert deployment_problems(relaxed) == []
    assert any("COOKIE_SECURE" in p for p in deployment_problems(make(environment="staging", cookie_secure=False)))