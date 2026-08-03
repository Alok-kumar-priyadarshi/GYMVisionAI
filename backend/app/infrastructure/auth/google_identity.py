# file_name: google_identity.py

"""Google identity verification.

``docs/09_security/47_SECURITY_ARCHITECTURE.md`` section 5 makes Google OAuth 2.0
the only authentication method in Version 1.

Verification sits behind an interface so the authentication flow can be built and
tested without contacting Google. The real implementation checks the token's
signature and audience with Google's library; tests use a fake. This is the same
adapter pattern the AI provider uses.
"""

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.config import Settings
from app.shared.exceptions import (
    AuthenticationUnavailableError,
    GoogleAuthenticationError,
)

logger = logging.getLogger(__name__)

GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

GOOGLE_TIMEOUT_SECONDS = 10
"""Deadline for a single attempt to reach Google.

The library's transport defaults to 120 seconds. That is far longer than a
person will wait at a sign-in button.
"""

CERTIFICATE_CACHE_SECONDS = 3600
"""How long Google's signing certificates are reused.

``google-auth`` refetches them on *every* verification, so each sign-in paid a
fresh HTTPS round trip to ``www.googleapis.com``. On a host whose route to that
name is slow the cost is severe: the name resolves to sixteen addresses, and
where the unreachable ones are tried first each attempt burns the full connect
timeout before the next is tried. Measured on the development machine that was
eighty seconds per login.

Google publishes these keys for hours and rotates them on a published schedule,
so holding them for an hour is well within their validity.
"""

CERTIFICATE_RETRY_AFTER_SECONDS = 300
"""Minimum age before a failed verification may refetch the certificates.

Serving a cached copy across a key rotation would reject every sign-in until the
entry expired, so a failure is allowed to refresh it. Without a floor, though,
any invalid token would force a refetch, handing anyone a way to make the server
hammer Google.
"""

CLOCK_SKEW_SECONDS = 10
"""Tolerance for clock drift between this server and Google.

Without it a machine a few seconds behind rejects freshly issued tokens with
"Token used too early", which looks like a credential problem and is not.
"""


@dataclass(frozen=True, slots=True)
class GoogleIdentity:
    """A verified Google account."""

    google_id: str
    email: str
    full_name: str
    picture: str | None = None
    email_verified: bool = True


@dataclass(frozen=True, slots=True)
class _CachedResponse:
    """The shape ``google.oauth2.id_token._fetch_certs`` reads from a response."""

    status: int
    data: bytes


class _CachingTransport:
    """A ``google-auth`` transport that reuses fetched certificates.

    Only successful ``GET`` responses are cached, so a transient failure is
    never remembered as an answer. The lock serialises the fetch itself: several
    people signing in at once would otherwise each start their own slow request
    for the same certificates.
    """

    def __init__(self, ttl_seconds: int = CERTIFICATE_CACHE_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[float, _CachedResponse]] = {}

    def __call__(self, url: str, method: str = "GET", **kwargs) -> _CachedResponse:
        from google.auth.transport import requests as google_requests

        with self._lock:
            entry = self._entries.get(url)
            if entry is not None and time.monotonic() - entry[0] < self._ttl:
                return entry[1]

            kwargs.setdefault("timeout", GOOGLE_TIMEOUT_SECONDS)
            response = google_requests.Request()(url, method=method, **kwargs)
            cached = _CachedResponse(status=response.status, data=response.data)

            if method == "GET" and response.status == 200:
                self._entries[url] = (time.monotonic(), cached)

            return cached

    def age_seconds(self) -> float | None:
        """Age of the oldest cached entry, or ``None`` when nothing is held."""
        with self._lock:
            if not self._entries:
                return None
            return time.monotonic() - min(stored for stored, _ in self._entries.values())

    def invalidate(self) -> None:
        """Drop every cached certificate."""
        with self._lock:
            self._entries.clear()


_CERTIFICATE_TRANSPORT = _CachingTransport()
"""Shared by every provider instance.

The dependency builds a new ``GoogleOAuthIdentityProvider`` per request, so a
cache held on the instance would be discarded before it was ever read. The
certificates belong to Google rather than to any one request, so one process-wide
cache is both correct and the only placement that works.
"""


class GoogleIdentityProvider(ABC):
    """Verifies a Google ID token and returns the account behind it."""

    @abstractmethod
    async def verify(self, id_token: str) -> GoogleIdentity:
        """Verify a Google ID token.

        Args:
            id_token: The token the frontend received from Google.

        Returns:
            The verified account.

        Raises:
            GoogleAuthenticationError: If the token is invalid, expired, issued
                for another application, or the email is unverified.
        """


class GoogleOAuthIdentityProvider(GoogleIdentityProvider):
    """Verifies tokens against Google's public keys."""

    def __init__(self, settings: Settings) -> None:
        """Create the provider.

        Raises:
            GoogleAuthenticationError: If no client identifier is configured.
                Without an audience to check against, any Google token from any
                application would be accepted.
        """
        if settings.google_client_id is None:
            raise GoogleAuthenticationError(
                "Google authentication is not configured."
            )
        self._client_id = settings.google_client_id.get_secret_value()
        self._transport = _CERTIFICATE_TRANSPORT

    def _verify_blocking(self, id_token: str) -> dict:
        """Verify a token against Google's public keys.

        Synchronous: the transport fetches Google's certificates over HTTPS the
        first time, and serves them from memory afterwards.
        """
        # Imported lazily so the backend runs without the dependency configured.
        from google.oauth2 import id_token as google_id_token

        return google_id_token.verify_oauth2_token(
            id_token,
            self._transport,
            self._client_id,
            clock_skew_in_seconds=CLOCK_SKEW_SECONDS,
        )

    def warm_certificate_cache(self) -> None:
        """Fetch Google's certificates ahead of the first sign-in.

        Called at startup so the one slow round trip is paid by the server
        starting up rather than by the first person to press the button.
        """
        from google.oauth2 import id_token as google_id_token

        # The cache is keyed by URL, so warming it has to use the very URL
        # `verify_oauth2_token` will ask for. That name is private, hence the
        # fallback to the published endpoint if the library ever renames it.
        certs_url = getattr(
            google_id_token,
            "_GOOGLE_OAUTH2_CERTS_URL",
            "https://www.googleapis.com/oauth2/v1/certs",
        )
        self._transport(certs_url, method="GET")

    async def verify(self, id_token: str) -> GoogleIdentity:
        try:
            # Off the event loop: verification may make a blocking HTTPS call to
            # fetch Google's certificates, and
            # `instructions/02_BACKEND_RULES.md` section 10 forbids blocking
            # inside an async handler. One slow call would otherwise stall every
            # concurrent request.
            claims = await asyncio.to_thread(self._verify_blocking, id_token)
        except ValueError as error:
            # The token itself is wrong: bad signature, wrong audience, expired
            # — or the cached certificates have been rotated out from under us.
            # Only an old enough cache is worth refetching to tell those apart.
            age = self._transport.age_seconds()
            if age is not None and age >= CERTIFICATE_RETRY_AFTER_SECONDS:
                logger.info("Refreshing Google certificates after a failure.")
                self._transport.invalidate()
                try:
                    claims = await asyncio.to_thread(self._verify_blocking, id_token)
                except ValueError as retry_error:
                    logger.warning("Google token verification failed.")
                    raise GoogleAuthenticationError() from retry_error
                except Exception as retry_error:
                    # Invalidating forces a fresh fetch, so this retry can fail
                    # for the same reasons the first fetch can. Catching only
                    # ValueError here let a transport failure escape `verify`
                    # entirely and surface as an unhandled 500.
                    logger.exception("Could not refresh Google's certificates.")
                    raise AuthenticationUnavailableError() from retry_error
            else:
                logger.warning("Google token verification failed.")
                raise GoogleAuthenticationError() from error
        except Exception as error:
            # Google could not be reached, or its certificates could not be
            # fetched. That is an outage on our side, not a bad credential, and
            # telling the user their sign-in failed would be misleading.
            logger.exception("Could not reach Google to verify the token.")
            raise AuthenticationUnavailableError() from error

        if claims.get("iss") not in GOOGLE_ISSUERS:
            logger.warning("Google token rejected: unexpected issuer.")
            raise GoogleAuthenticationError()

        if not claims.get("email_verified", False):
            logger.warning("Google token rejected: unverified email.")
            raise GoogleAuthenticationError(
                "The Google account's email address is not verified."
            )

        subject = claims.get("sub")
        email = claims.get("email")
        if not subject or not email:
            raise GoogleAuthenticationError()

        return GoogleIdentity(
            google_id=subject,
            email=email,
            full_name=claims.get("name") or email.split("@")[0],
            picture=claims.get("picture"),
            email_verified=True,
        )
