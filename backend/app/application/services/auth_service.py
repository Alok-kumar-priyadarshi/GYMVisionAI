# file_name: auth_service.py

"""Authentication use cases.

``instructions/02_BACKEND_RULES.md`` section 5 puts business logic in the service
layer and keeps SQL out of it. This service coordinates the identity provider,
the repositories and the token service; it executes no queries itself.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from app.core.security import TokenPair, TokenService, TokenType
from app.domain.entities.progress import Progress
from app.domain.entities.user import User
from app.domain.repositories.progress_repository import ProgressRepository
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.auth.google_identity import GoogleIdentityProvider
from app.shared.exceptions import UserNotFoundError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoginResult:
    """The outcome of a successful login."""

    user: User
    tokens: TokenPair
    is_new_user: bool


class AuthService:
    """Signs users in with Google and issues application tokens."""

    def __init__(
        self,
        users: UserRepository,
        progress: ProgressRepository,
        identity_provider: GoogleIdentityProvider,
        tokens: TokenService,
    ) -> None:
        self._users = users
        self._progress = progress
        self._identity = identity_provider
        self._tokens = tokens

    async def login_with_google(self, id_token: str) -> LoginResult:
        """Verify a Google token, provision the user, and issue tokens.

        A first-time user is created along with an empty progress record, so
        every later read has something to return.

        Args:
            id_token: The Google ID token supplied by the frontend.

        Returns:
            The user and their tokens.

        Raises:
            GoogleAuthenticationError: If Google rejects the token.
        """
        identity = await self._identity.verify(id_token)

        user = await self._users.get_by_google_id(identity.google_id)
        is_new_user = user is None

        if user is None:
            user = await self._provision(identity)
        else:
            user = await self._refresh_profile(user, identity)

        # Identifiers are logged; email addresses are not.
        logger.info("User authenticated: %s", user.id)
        return LoginResult(
            user=user, tokens=self._tokens.issue(user.id), is_new_user=is_new_user
        )

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, int]:
        """Exchange a refresh token for a new access token.

        Returns:
            The new access token and its lifetime in seconds.

        Raises:
            InvalidTokenError: If the token is not a valid refresh token.
            ExpiredTokenError: If the refresh token has expired.
            UserNotFoundError: If the user no longer exists.
        """
        claims = self._tokens.verify(refresh_token, TokenType.REFRESH)

        if not await self._users.exists(claims.subject):
            raise UserNotFoundError()

        return self._tokens.issue_access_token(claims.subject)

    async def current_user(self, user_id: UUID) -> User:
        """Return the authenticated user.

        Raises:
            UserNotFoundError: If the user no longer exists.
        """
        user = await self._users.get(user_id)
        if user is None:
            raise UserNotFoundError()
        return user

    async def _provision(self, identity) -> User:
        """Create a first-time user and their progress record."""
        user = User(
            google_id=identity.google_id,
            email=identity.email,
            full_name=identity.full_name,
            profile_picture=identity.picture,
        )
        user.activate()

        stored = await self._users.add(user)
        await self._progress.add(Progress(user_id=stored.id))
        logger.info("New user provisioned: %s", stored.id)
        return stored

    async def _refresh_profile(self, user: User, identity) -> User:
        """Update a returning user's details if Google's have changed."""
        changed = (
            user.full_name != identity.full_name
            or user.profile_picture != identity.picture
            or user.email != identity.email
        )
        if not changed:
            return user

        user.email = identity.email
        user.full_name = identity.full_name
        user.profile_picture = identity.picture
        user.touch()
        return await self._users.update(user)
