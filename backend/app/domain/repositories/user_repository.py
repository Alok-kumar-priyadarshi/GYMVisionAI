# file_name: user_repository.py

"""Repository interfaces for the user domain.

``docs/04_backend/26_PERSISTENCE_LAYER.md`` section 6 gives every aggregate
exactly one repository, and section 14 requires repositories to return domain
objects and keep SQL isolated.

These are interfaces only. They are declared in the domain so that dependencies
point inward: infrastructure implements them, and no business code depends on a
database. Methods are asynchronous per ``instructions/02_BACKEND_RULES.md``
section 10.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.user import BodyProfile, User


class UserRepository(ABC):
    """Persistence for the ``User`` aggregate."""

    @abstractmethod
    async def get(self, user_id: UUID) -> User | None:
        """Return a user by identifier, or ``None`` if absent."""

    @abstractmethod
    async def get_by_google_id(self, google_id: str) -> User | None:
        """Return a user by their Google identity, or ``None`` if absent.

        Used by the authentication flow, which knows the external identity
        before it knows the internal one.
        """

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        """Return a user by email address, or ``None`` if absent."""

    @abstractmethod
    async def add(self, user: User) -> User:
        """Persist a new user and return the stored entity."""

    @abstractmethod
    async def update(self, user: User) -> User:
        """Persist changes to an existing user."""

    @abstractmethod
    async def exists(self, user_id: UUID) -> bool:
        """Report whether a user exists."""


class BodyProfileRepository(ABC):
    """Persistence for the ``BodyProfile`` owned by a user."""

    @abstractmethod
    async def get_for_user(self, user_id: UUID) -> BodyProfile | None:
        """Return a user's body profile, or ``None`` if not yet created."""

    @abstractmethod
    async def add(self, profile: BodyProfile) -> BodyProfile:
        """Persist a new body profile."""

    @abstractmethod
    async def update(self, profile: BodyProfile) -> BodyProfile:
        """Persist changes to an existing body profile."""
