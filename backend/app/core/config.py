from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    cors_origins: list[str] = ["http://localhost:5173"]
    secret_key: str
    access_token_expire_minutes: int =60
    cookie_secure: bool = False

settings = Settings()