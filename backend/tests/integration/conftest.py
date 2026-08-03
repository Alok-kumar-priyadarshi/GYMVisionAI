# file_name: conftest.py

"""Fixtures for API integration tests.

The tests run against a real application, a real database schema and the real
engines. Only two things are substituted:

- SQLite replaces PostgreSQL, because no PostgreSQL is available here. The
  portable column types mean the same mapping code runs either way.
- A fake Google identity provider replaces the real one, because verifying a
  token requires contacting Google. Everything after verification is real.
"""

from typing import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.routers import exercises as exercises_router
from app.core.config import Settings
from app.core.dependencies import get_identity_provider
from app.infrastructure.auth.google_identity import (
    GoogleIdentity,
    GoogleIdentityProvider,
)
from app.infrastructure.database import models  # noqa: F401 - registers tables
from app.infrastructure.database.session import Base, configure_database, get_session
from app.infrastructure.seed import seed_all
from app.main import create_app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class FakeGoogleIdentityProvider(GoogleIdentityProvider):
    """Returns a scripted identity instead of contacting Google."""

    def __init__(self) -> None:
        self.identities: dict[str, GoogleIdentity] = {
            "token-alice": GoogleIdentity(
                google_id="google-alice",
                email="alice@test.com",
                full_name="Alice Tester",
                picture="https://example.test/alice.png",
            ),
            "token-bob": GoogleIdentity(
                google_id="google-bob",
                email="bob@test.com",
                full_name="Bob Tester",
            ),
        }

    async def verify(self, id_token: str) -> GoogleIdentity:
        from app.shared.exceptions import GoogleAuthenticationError

        identity = self.identities.get(id_token)
        if identity is None:
            raise GoogleAuthenticationError()
        return identity


def test_settings() -> Settings:
    """Settings for a fully configured test deployment."""
    return Settings(
        environment="development",
        jwt_secret_key="test-signing-key-not-a-real-secret",
        google_client_id="test-client-id",
        google_client_secret="test-client-secret",
        database_url=TEST_DATABASE_URL,
        groq_api_key=None,
    )


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Create a fresh schema and seed it from configuration."""
    engine = configure_database(TEST_DATABASE_URL)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:
        await seed_all(session)
        await session.commit()

    yield factory
    await engine.dispose()


@pytest.fixture
def client(session_factory) -> Iterator[TestClient]:
    """An API client wired to the test database and a fake Google."""
    application = create_app(test_settings())

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fake_google = FakeGoogleIdentityProvider()
    application.dependency_overrides[get_session] = override_session
    application.dependency_overrides[get_identity_provider] = lambda: fake_google

    # Detector state is process-global; clear it so tests cannot leak into
    # each other.
    exercises_router._LIVE_SESSIONS.clear()

    with TestClient(application) as test_client:
        yield test_client

    application.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """Sign in as Alice and return her authorization header."""
    response = client.post("/api/v1/auth/google", json={"idToken": "token-alice"})
    assert response.status_code == 200, response.text
    token = response.json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def profiled_headers(client: TestClient, auth_headers: dict[str, str]):
    """Alice, with a body profile created."""
    response = client.put(
        "/api/v1/users/profile",
        headers=auth_headers,
        json={
            "age": 30,
            "gender": "Male",
            "heightCm": 178,
            "weightKg": 78,
            "fitnessGoal": "General Fitness",
            "fitnessLevel": "Intermediate",
            "problemAreas": ["belly"],
            "workoutDurationMinutes": 45,
        },
    )
    assert response.status_code == 200, response.text
    return auth_headers
