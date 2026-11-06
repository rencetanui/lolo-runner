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
settings = Settings()   