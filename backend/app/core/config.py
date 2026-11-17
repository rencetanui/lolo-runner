from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    cors_origins: list[str] = ["http://localhost:5173"]
    secret_key: str
    access_token_expire_minutes: int =60
    cookie_secure: bool = False
    registration_hold_minutes: int =30
    mpesa_env: str = "mock"              # "mock", "sandbox" or "production"
    mpesa_consumer_key: str = ""
    mpesa_consumer_secret: str = ""
    mpesa_shortcode: str = ""
    mpesa_passkey: str = ""
    mpesa_party_b: str = ""              # empty for Paybill; the till number for Buy Goods
    mpesa_transaction_type: str = "CustomerPayBillOnline"
    mpesa_callback_secret: str = ""
    mpesa_verify_callbacks: bool | None = None   # None = on in production, off elsewhere
    mpesa_callback_ips: str = ""                 # comma-separated allowlist. Empty = no IP check.
    media_dir: str = "media"
    max_upload_mb: int = 5
    
    public_base_url: str = ""            # public HTTPS URL of this API (your tunnel URL in dev)
    
    google_client_id: str = ""
    
    app_name: str = "Lolo Runner"
    frontend_url: str = "http://localhost:5173"

    email_backend: str = "console"        # "console" (log only) or "smtp"
    email_from: str = "no-reply@example.com"
    email_from_name: str = "Lolo Runner"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False

    sms_backend: str = "console"          # "console" (log only) or "africastalking"
    at_env: str = "sandbox"               # "sandbox" or "production"
    at_username: str = "sandbox"
    at_api_key: str = ""
    at_sender_id: str = ""
    require_email_verification: bool = True
    verify_token_hours: int = 48
    reset_token_minutes: int = 60
    trusted_proxies: int = 0     # how many reverse proxies sit in front of the API (0 in development)
    require_terms_acceptance: bool = True
    
    
    environment: str = "development"      # development | staging | production
    sentry_dsn: str = ""
settings = Settings()   

def deployment_problems(s: Settings) -> list[str]:
    """Settings that must never be wrong on a real server. An empty list means fine."""
    if s.environment not in ("staging", "production"):
        return []
    problems: list[str] = []
    if len(s.secret_key) < 32 or s.secret_key.lower().startswith(("replace", "change", "dev", "test")):
        problems.append("SECRET_KEY must be a long random value (at least 32 characters).")
    if not s.cookie_secure:
        problems.append("COOKIE_SECURE must be true, so session cookies only travel over HTTPS.")
    if s.trusted_proxies < 1:
        problems.append("TRUSTED_PROXIES must be 1 behind Caddy, or every visitor looks like one IP to the rate limiter.")
    for name in ("frontend_url", "public_base_url"):
        if not getattr(s, name).startswith("https://"):
            problems.append(f"{name.upper()} must start with https://")
    if not s.cors_origins or any(not origin.startswith("https://") for origin in s.cors_origins):
        problems.append("CORS_ORIGINS must list only your https:// site.")
    if len(s.mpesa_callback_secret) < 24:
        problems.append("MPESA_CALLBACK_SECRET must be a long random value (at least 24 characters).")
    if not s.require_email_verification:
        problems.append("REQUIRE_EMAIL_VERIFICATION must be true.")
    if not s.require_terms_acceptance:
        problems.append("REQUIRE_TERMS_ACCEPTANCE must be true.")
    if s.environment == "production":
        if s.mpesa_env != "production":
            problems.append(f"MPESA_ENV is '{s.mpesa_env}'. Production must use 'production'.")
        else:
            missing = [n for n, v in (
                ("MPESA_CONSUMER_KEY", s.mpesa_consumer_key), ("MPESA_CONSUMER_SECRET", s.mpesa_consumer_secret),
                ("MPESA_SHORTCODE", s.mpesa_shortcode), ("MPESA_PASSKEY", s.mpesa_passkey)) if not v]
            if missing:
                problems.append("Missing M-Pesa settings: " + ", ".join(missing) + ".")
        if s.email_backend != "smtp" or s.smtp_host in ("", "localhost"):
            problems.append("EMAIL_BACKEND must be 'smtp' with a real SMTP_HOST, or nobody receives any email.")
        if s.sms_backend != "africastalking" or s.at_env != "production" or not s.at_api_key:
            problems.append("SMS must use Africa's Talking in production mode (SMS_BACKEND, AT_ENV, AT_API_KEY).")
    return problems