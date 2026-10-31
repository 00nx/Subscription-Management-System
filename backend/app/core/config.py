from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    secret_key: str = Field(min_length=32)  # required, no default: a secret is never baked into the code
    database_url: str = "sqlite:///./brightloop.db"  # SQLite by default (demo); PostgreSQL: postgresql+psycopg://user:pass@host/db
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:5173"]

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False  # set true behind HTTPS
    rate_limit_per_minute: int = 10
    rate_limit_refresh_per_minute: int = 60
    max_failed_logins: int = 5  # consecutive failures before the account is locked
    lockout_minutes: int = 15

    frontend_url: str = "http://localhost:5173"
    password_reset_expire_minutes: int = 60
    smtp_host: str = ""  # empty = emails are written to the log instead of sent
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "Brightloop <noreply@brightloop.local>"
    email_delivery: str = "auto"  # auto = Celery if the broker is reachable else a thread; celery | thread | inline (tests) | off (log only, nothing is sent)

    allow_overpayment: bool = False

    # Razorpay TEST MODE only (rzp_test_ keys). Live keys are refused by the integration.
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_api_base: str = "https://api.razorpay.com/v1"

    # Business identity printed on invoice PDFs (set in .env; nothing here is a secret)
    business_name: str = "Brightloop"
    business_tagline: str = "Subscription management"
    business_address: str = ""
    business_email: str = ""
    business_phone: str = ""
    business_tax_id: str = ""  # e.g. GSTIN
    payment_instructions: str = "Pay online from your Brightloop customer portal, or by bank transfer quoting the invoice number."
    auto_confirm_invoices: bool = False  # billing engine creates DRAFT invoices unless true

    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
