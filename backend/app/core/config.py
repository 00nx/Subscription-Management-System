from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    secret_key: str = Field(min_length=32)  # required, no default: a secret is never baked into the code
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:5173"]

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False  # set true behind HTTPS
    rate_limit_per_minute: int = 10

    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
