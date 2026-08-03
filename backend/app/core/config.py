# file_name: config.py

"""Application configuration.

Configuration is loaded once from environment variables and is immutable at
runtime, per ``instructions/02_BACKEND_RULES.md`` section 11.

Secrets are declared here but never defaulted to a real value.
``docs/09_security/47_SECURITY_ARCHITECTURE.md`` section 11 requires them to come
from the environment, to stay out of source control and never to reach the
frontend. ``SecretStr`` keeps them out of logs and tracebacks.

The application deliberately starts without secrets in development, so the
backend can be built and tested before credentials exist. Production is strict:
:meth:`Settings.validate_for_runtime` refuses to start when a required secret is
missing, which satisfies the "fail securely" principle in section 3.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


MINIMUM_JWT_KEY_LENGTH = 32
"""Shortest signing key accepted, per RFC 7518 section 3.2 for HS256."""


class Environment(StrEnum):
    """Deployment environments the backend recognises."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Logging levels supported by the monitoring architecture, section 6."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Every value the backend reads from its environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # Application
    app_name: str = "GymVision AI"
    environment: Environment = Environment.DEVELOPMENT
    api_v1_prefix: str = "/api/v1"

    # Observability
    log_level: LogLevel = LogLevel.INFO
    json_logs: bool = False

    # Cross-origin access
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)

    # Secrets. Absent in development, required in production.
    google_client_id: SecretStr | None = None
    google_client_secret: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    database_url: SecretStr | None = None
    jwt_secret_key: SecretStr | None = None

    # AI subsystem
    ai_model: str = "llama-3.3-70b-versatile"
    ai_temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    ai_max_tokens: int = Field(default=800, ge=64, le=8192)
    ai_timeout_seconds: float = Field(default=20.0, gt=0, le=120)

    # Token policy
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=30, ge=1, le=365)

    @field_validator("database_url", mode="before")
    @classmethod
    def _use_an_async_driver(cls, value: object) -> object:
        """Rewrite a synchronous PostgreSQL URL to the async driver.

        Managed platforms hand out ``postgres://`` or ``postgresql://`` URLs.
        Both select a synchronous driver, which fails at startup with an
        unhelpful import error. The scheme is corrected here instead.
        """
        if value is None:
            return None

        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        if not raw:
            return None

        for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
            if raw.startswith(prefix):
                return "postgresql+asyncpg://" + raw[len(prefix) :]
        return raw

    @field_validator("jwt_secret_key", mode="after")
    @classmethod
    def _reject_a_weak_signing_key(cls, value: SecretStr | None) -> SecretStr | None:
        """Refuse a signing key short enough to be brute-forced.

        RFC 7518 section 3.2 requires an HMAC key at least as long as the hash
        output, which is 32 bytes for SHA-256. A short key would sign tokens
        that look valid and are forgeable.
        """
        if value is None:
            return None

        if len(value.get_secret_value()) < MINIMUM_JWT_KEY_LENGTH:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {MINIMUM_JWT_KEY_LENGTH} "
                "characters. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated list, which is how platforms pass lists."""
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @model_validator(mode="after")
    def _reject_wildcard_origins_in_production(self) -> "Settings":
        """Wildcard origins are prohibited in production, per section 13."""
        if self.is_production and "*" in self.cors_origins:
            raise ValueError("wildcard CORS origins are not allowed in production")
        return self

    @property
    def is_production(self) -> bool:
        """Report whether the backend is running in production."""
        return self.environment is Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Report whether the backend is running in development."""
        return self.environment is Environment.DEVELOPMENT

    @property
    def docs_url(self) -> str | None:
        """Return the OpenAPI docs path, which production does not expose."""
        return None if self.is_production else "/docs"

    def missing_secrets(self) -> tuple[str, ...]:
        """Return the names of secrets that have not been supplied.

        Used by the readiness check to report which capabilities are unavailable
        without leaking any secret value.
        """
        required = {
            "google_client_id": self.google_client_id,
            "google_client_secret": self.google_client_secret,
            "groq_api_key": self.groq_api_key,
            "database_url": self.database_url,
            "jwt_secret_key": self.jwt_secret_key,
        }
        return tuple(name for name, value in required.items() if value is None)

    def validate_for_runtime(self) -> None:
        """Refuse to start a production deployment with missing secrets.

        Raises:
            ValueError: If the environment is production and a secret is absent.
        """
        if not self.is_production:
            return

        missing = self.missing_secrets()
        if missing:
            raise ValueError(
                "production requires these environment variables: "
                + ", ".join(sorted(name.upper() for name in missing))
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the application settings, loading them once.

    Cached so configuration is read a single time and shared, and so FastAPI can
    depend on it without re-reading the environment per request.
    """
    return Settings()
