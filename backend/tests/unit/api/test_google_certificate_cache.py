# file_name: test_google_certificate_cache.py

"""The certificate cache behind Google token verification.

``google-auth`` refetches Google's signing certificates on every verification.
Where the route to ``www.googleapis.com`` is slow that round trip dominates
sign-in, so the transport caches them. These tests pin the behaviour that makes
the cache safe to rely on.
"""

from dataclasses import dataclass

import pytest

from app.infrastructure.auth import google_identity
from app.infrastructure.auth.google_identity import _CachingTransport


@dataclass
class FakeResponse:
    """Mirrors the attributes ``_fetch_certs`` reads."""

    status: int
    data: bytes


class FakeTransport:
    """Counts how often the network was actually used."""

    def __init__(self, *responses: FakeResponse) -> None:
        self._responses = list(responses) or [FakeResponse(200, b"{}")]
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, url: str, method: str = "GET", **kwargs) -> FakeResponse:
        self.calls.append((url, method, kwargs))
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


@pytest.fixture
def network(monkeypatch: pytest.MonkeyPatch) -> FakeTransport:
    """Replace the real HTTPS transport with a counting fake."""
    fake = FakeTransport()
    monkeypatch.setattr(
        "google.auth.transport.requests.Request", lambda: fake, raising=True
    )
    return fake


CERTS_URL = "https://www.googleapis.com/oauth2/v1/certs"


def test_second_fetch_is_served_from_memory(network: FakeTransport) -> None:
    transport = _CachingTransport()

    first = transport(CERTS_URL)
    second = transport(CERTS_URL)

    assert first.data == second.data
    # The whole point: one network call, not two.
    assert len(network.calls) == 1


def test_a_deadline_is_applied_to_the_fetch(network: FakeTransport) -> None:
    # Without one the library waits its own 120 seconds, far longer than a
    # person will hold at a sign-in button.
    _CachingTransport()(CERTS_URL)

    _, _, kwargs = network.calls[0]
    assert kwargs["timeout"] == google_identity.GOOGLE_TIMEOUT_SECONDS


def test_a_failed_response_is_not_remembered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Caching a 500 would turn a blip into an hour of broken sign-in.
    fake = FakeTransport(FakeResponse(500, b""), FakeResponse(200, b"{}"))
    monkeypatch.setattr("google.auth.transport.requests.Request", lambda: fake)
    transport = _CachingTransport()

    assert transport(CERTS_URL).status == 500
    assert transport(CERTS_URL).status == 200
    assert len(fake.calls) == 2


def test_the_entry_expires(network: FakeTransport) -> None:
    transport = _CachingTransport(ttl_seconds=0)

    transport(CERTS_URL)
    transport(CERTS_URL)

    assert len(network.calls) == 2


def test_invalidate_forces_a_refetch(network: FakeTransport) -> None:
    # Used when a verification fails against certificates Google has rotated.
    transport = _CachingTransport()

    transport(CERTS_URL)
    transport.invalidate()
    transport(CERTS_URL)

    assert len(network.calls) == 2


def test_age_reports_nothing_when_empty(network: FakeTransport) -> None:
    transport = _CachingTransport()

    assert transport.age_seconds() is None

    transport(CERTS_URL)
    age = transport.age_seconds()

    assert age is not None and age >= 0


def test_providers_share_one_cache() -> None:
    """A provider is built per request, so the cache cannot live on it.

    This is the mistake the caching originally shipped with: an instance-level
    cache was allocated and discarded on every single request, so it never
    returned a hit and the slow fetch happened every time regardless.
    """
    from pydantic import SecretStr

    from app.core.config import Settings
    from app.infrastructure.auth.google_identity import GoogleOAuthIdentityProvider

    settings = Settings(
        google_client_id=SecretStr("test.apps.googleusercontent.com"),
        jwt_secret_key=SecretStr("x" * 40),
        database_url="sqlite+aiosqlite:///:memory:",
    )

    first = GoogleOAuthIdentityProvider(settings)
    second = GoogleOAuthIdentityProvider(settings)

    assert first._transport is second._transport
