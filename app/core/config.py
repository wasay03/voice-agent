"""Typed application settings, read once from the environment (and `.env` locally)."""

from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Query parameters libpq understands but asyncpg rejects (Neon adds channel_binding by default).
_UNSUPPORTED_DSN_PARAMS = frozenset({"channel_binding"})
_POSTGRES_SCHEMES = frozenset({"postgres", "postgresql", "postgresql+asyncpg"})


def normalize_dsn(dsn: str) -> str:
    """Return a DSN asyncpg accepts: plain `postgresql://` scheme, unsupported params removed."""
    parts = urlsplit(dsn.strip())
    scheme = "postgresql" if parts.scheme in _POSTGRES_SCHEMES else parts.scheme
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in _UNSUPPORTED_DSN_PARAMS]
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    # Database
    database_url: str
    db_pool_min: int = 1
    db_pool_max: int = 5
    db_statement_timeout_ms: int = 3000
    db_max_inactive_conn_seconds: float = 60.0

    # Auth
    api_key: SecretStr
    vapi_webhook_secret: SecretStr

    # Vapi management (only scripts/sync_assistant.py uses these; the running service never does)
    vapi_api_key: SecretStr | None = None
    vapi_phone_number_id: str | None = None

    # Clinic / agent
    public_base_url: str = ""
    clinic_name: str = "Riverside Family Clinic"
    agent_name: str = "Ava"
    clinic_tz: str = "America/New_York"
    tool_timeout_seconds: float = 4.0

    # Dashboard (bonus)
    dashboard_user: str = "admin"
    dashboard_password: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_dsn(value)

    @field_validator("clinic_tz")
    @classmethod
    def _validate_tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown time zone {value!r}") from exc
        return value

    @property
    def json_logs(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
