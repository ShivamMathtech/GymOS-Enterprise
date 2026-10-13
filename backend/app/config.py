from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str
    secret_key: str
    frontend_url: str = "http://localhost:5173"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_pool_size: int = 10
    access_minutes: int = 10
    refresh_days: int = 7
    cookie_secure: bool = False
    allow_registration: bool = True
    upload_dir: Path = Path("var/uploads")
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "gymos@example.com"
    smtp_starttls: bool = True
    auth_rate_limit: int = 15

    @model_validator(mode="after")
    def validate_security(self):
        if len(self.secret_key) < 32 or self.secret_key.startswith("CHANGE_"):
            raise ValueError("SECRET_KEY must be a random secret of at least 32 characters. Run scripts/configure.py.")
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg://")
        if self.app_env == "production" and (
            not self.cookie_secure or not self.frontend_url.startswith("https://") or self.allow_registration
        ):
            raise ValueError("Production requires HTTPS, COOKIE_SECURE=true and ALLOW_REGISTRATION=false")
        return self

    @property
    def origins(self):
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]


@lru_cache
def settings():
    return Settings()
