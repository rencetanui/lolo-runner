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
    public_base_url: str = ""            # public HTTPS URL of this API (your tunnel URL in dev)
    
settings = Settings()