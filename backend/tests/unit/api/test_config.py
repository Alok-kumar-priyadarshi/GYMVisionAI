# file_name: test_config.py

"""Unit tests for application configuration."""

import pytest

from app.core.config import Environment, LogLevel, Settings


def settings(**overrides) -> Settings:
    defaults = {
        "environment": "development",
        "google_client_id": None,
        "google_client_secret": None,
        "groq_api_key": None,
        "database_url": None,
        "jwt_secret_key": None,
    }
    return Settings(**{**defaults, **overrides})


def test_defaults_are_safe_for_local_development():
    built = settings()

    assert built.environment is Environment.DEVELOPMENT
    assert built.log_level is LogLevel.INFO
    assert built.api_v1_prefix == "/api/v1"


def test_settings_are_immutable():
    with pytest.raises(Exception):
        settings().environment = "production"


def test_secrets_default_to_absent():
    # The backend must start before credentials exist.
    assert set(settings().missing_secrets()) == {
        "google_client_id",
        "google_client_secret",
        "groq_api_key",
        "database_url",
        "jwt_secret_key",
    }


def test_supplied_secrets_are_not_reported_as_missing():
    built = settings(groq_api_key="test-key")

    assert "groq_api_key" not in built.missing_secrets()


def test_secret_values_are_hidden_from_output():
    built = settings(jwt_secret_key="super-secret-value-that-is-long-enough-ok")

    assert "super-secret-value" not in str(built)
    assert "super-secret-value" not in repr(built)


def test_secrets_must_be_read_explicitly():
    built = settings(groq_api_key="test-key")

    assert built.groq_api_key.get_secret_value() == "test-key"


def test_development_starts_without_credentials():
    settings().validate_for_runtime()


def test_production_refuses_to_start_without_credentials():
    with pytest.raises(ValueError) as error:
        settings(environment="production").validate_for_runtime()

    message = str(error.value)
    assert "GOOGLE_CLIENT_ID" in message
    assert "JWT_SECRET_KEY" in message


def test_production_starts_when_every_secret_is_present():
    settings(
        environment="production",
        google_client_id="id",
        google_client_secret="secret",
        groq_api_key="key",
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret_key="a-test-signing-key-of-sufficient-length",
    ).validate_for_runtime()


def test_cors_origins_accept_a_comma_separated_list():
    built = settings(cors_origins="http://a.test, http://b.test")

    assert built.cors_origins == ("http://a.test", "http://b.test")


def test_wildcard_origins_are_allowed_in_development():
    assert "*" in settings(cors_origins="*").cors_origins


def test_wildcard_origins_are_rejected_in_production():
    with pytest.raises(Exception) as error:
        settings(
            environment="production",
            cors_origins="*",
            google_client_id="id",
            google_client_secret="secret",
            groq_api_key="key",
            database_url="sqlite+aiosqlite:///:memory:",
            jwt_secret_key="a-test-signing-key-of-sufficient-length",
        )

    assert "wildcard" in str(error.value)


def test_production_hides_the_api_documentation():
    built = settings(
        environment="production",
        google_client_id="id",
        google_client_secret="secret",
        groq_api_key="key",
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret_key="a-test-signing-key-of-sufficient-length",
    )

    assert built.docs_url is None
    assert built.is_production is True


def test_development_exposes_the_api_documentation():
    assert settings().docs_url == "/docs"


def test_token_lifetimes_are_bounded():
    with pytest.raises(Exception):
        settings(access_token_expire_minutes=0)


@pytest.mark.parametrize(
    "supplied",
    [
        "postgres://user:pass@host:5432/db",
        "postgresql://user:pass@host:5432/db",
        "postgresql+psycopg2://user:pass@host:5432/db",
    ],
)
def test_synchronous_database_urls_are_rewritten_for_async(supplied):
    # Managed platforms hand out synchronous URLs, which would fail at startup.
    built = settings(database_url=supplied)

    assert built.database_url.get_secret_value().startswith("postgresql+asyncpg://")
    assert built.database_url.get_secret_value().endswith("@host:5432/db")


def test_an_async_database_url_is_left_alone():
    built = settings(database_url="postgresql+asyncpg://user:pass@host/db")

    assert built.database_url.get_secret_value() == (
        "postgresql+asyncpg://user:pass@host/db"
    )


def test_a_blank_database_url_is_treated_as_absent():
    assert settings(database_url="").database_url is None


@pytest.mark.parametrize("weak", ["short", "a" * 31, ""])
def test_a_weak_signing_key_is_rejected(weak):
    # RFC 7518 requires at least 32 bytes for HS256; a shorter key is forgeable.
    with pytest.raises(Exception) as error:
        settings(jwt_secret_key=weak)

    assert "32" in str(error.value)


def test_a_sufficiently_long_signing_key_is_accepted():
    key = "a" * 32

    assert settings(jwt_secret_key=key).jwt_secret_key.get_secret_value() == key
