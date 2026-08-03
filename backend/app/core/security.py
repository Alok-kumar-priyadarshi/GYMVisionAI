# file_name: security.py

"""Token issuing and verification.

``docs/09_security/47_SECURITY_ARCHITECTURE.md`` section 7 makes a session a
signed, time-limited, stateless JWT. Section 20 forbids hardcoded secrets, so the
signing key comes from configuration and the service refuses to run without it.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID

import jwt

from app.core.config import Settings
from app.shared.exceptions import (
    AuthenticationUnavailableError,
    ExpiredTokenError,
    InvalidTokenError,
)

logger = logging.getLogger(__name__)


class TokenType(StrEnum):
    """Kinds of token the backend issues."""

    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True, slots=True)
class TokenPair:
    """An access token and the refresh token that renews it."""

    access_token: str
    refresh_token: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """The verified contents of a token."""

    subject: UUID
    token_type: TokenType
    expires_at: datetime


class TokenService:
    """Creates and verifies JSON Web Tokens."""

    def __init__(self, settings: Settings) -> None:
        """Create the service.

        Construction never fails on a missing key. The service is built as a
        request dependency, so raising here would turn every unauthenticated
        request into a server error instead of a clean 401. Issuing or verifying
        without a key raises instead.
        """
        self._key = (
            settings.jwt_secret_key.get_secret_value()
            if settings.jwt_secret_key is not None
            else None
        )
        self._algorithm = settings.jwt_algorithm
        self._access_ttl = timedelta(minutes=settings.access_token_expire_minutes)
        self._refresh_ttl = timedelta(days=settings.refresh_token_expire_days)

    @property
    def is_configured(self) -> bool:
        """Report whether a signing key is available."""
        return self._key is not None

    @property
    def access_token_seconds(self) -> int:
        """Return the access token lifetime in seconds."""
        return int(self._access_ttl.total_seconds())

    def _require_key(self) -> str:
        """Return the signing key.

        Raises:
            AuthenticationUnavailableError: If none is configured. The reason is
                logged for operators and withheld from the client.
        """
        if self._key is None:
            logger.error("JWT_SECRET_KEY is not configured; tokens are unavailable.")
            raise AuthenticationUnavailableError()
        return self._key

    def issue(self, user_id: UUID) -> TokenPair:
        """Issue a fresh access and refresh token for a user."""
        return TokenPair(
            access_token=self._create(user_id, TokenType.ACCESS, self._access_ttl),
            refresh_token=self._create(user_id, TokenType.REFRESH, self._refresh_ttl),
            expires_in=self.access_token_seconds,
        )

    def issue_access_token(self, user_id: UUID) -> tuple[str, int]:
        """Issue only an access token, for the refresh endpoint."""
        return (
            self._create(user_id, TokenType.ACCESS, self._access_ttl),
            self.access_token_seconds,
        )

    def verify(self, token: str, expected: TokenType) -> TokenClaims:
        """Verify a token and return its claims.

        Args:
            token: The encoded token.
            expected: The token type the caller requires.

        Returns:
            The verified claims.

        Raises:
            ExpiredTokenError: If the token has expired.
            InvalidTokenError: If the signature, contents or type are wrong.
        """
        key = self._require_key()

        try:
            payload = jwt.decode(token, key, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as error:
            raise ExpiredTokenError() from error
        except jwt.InvalidTokenError as error:
            raise InvalidTokenError() from error

        if payload.get("type") != str(expected):
            # A refresh token must never be accepted where access is required.
            logger.warning("Token rejected: wrong token type.")
            raise InvalidTokenError()

        try:
            subject = UUID(payload["sub"])
        except (KeyError, ValueError, TypeError) as error:
            raise InvalidTokenError() from error

        return TokenClaims(
            subject=subject,
            token_type=expected,
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )

    def _create(self, user_id: UUID, token_type: TokenType, ttl: timedelta) -> str:
        """Encode one token."""
        issued_at = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "type": str(token_type),
            "iat": issued_at,
            "exp": issued_at + ttl,
        }
        return jwt.encode(payload, self._require_key(), algorithm=self._algorithm)
