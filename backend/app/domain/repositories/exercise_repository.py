# file_name: exercise_repository.py

"""Repository interfaces for the exercise domain."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.exercise import Exercise, ExerciseResult, ExerciseSession
from app.domain.value_objects.enums import ExerciseCategory


class ExerciseRepository(ABC):
    """Persistence for the ``Exercise`` aggregate.

    Exercise metadata is read-only at runtime, so this interface has no update
    or delete method. The library changes by re-seeding from configuration.
    """

    @abstractmethod
    async def get(self, exercise_id: UUID) -> Exercise | None:
        """Return an exercise by identifier, or ``None`` if absent."""

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Exercise | None:
        """Return an exercise by slug, or ``None`` if absent."""

    @abstractmethod
    async def list_supported(self) -> tuple[Exercise, ...]:
        """Return every supported exercise."""

    @abstractmethod
    async def list_by_category(
        self, category: ExerciseCategory
    ) -> tuple[Exercise, ...]:
        """Return every supported exercise in one category."""

    @abstractmethod
    async def upsert_many(self, exercises: tuple[Exercise, ...]) -> int:
        """Seed or refresh the library from configuration.

        Returns:
            The number of exercises written.
        """


class ExerciseSessionRepository(ABC):
    """Persistence for the ``ExerciseSession`` aggregate and its results."""

    @abstractmethod
    async def get(self, session_id: UUID) -> ExerciseSession | None:
        """Return a session by identifier, or ``None`` if absent."""

    @abstractmethod
    async def get_active_for_user(self, user_id: UUID) -> ExerciseSession | None:
        """Return a user's active session, or ``None`` if none is running.

        ``contracts/exercises/01_START_SESSION.md`` allows only one active
        session per user, and this is how that rule is enforced.
        """

    @abstractmethod
    async def list_for_user(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> tuple[ExerciseSession, ...]:
        """Return a user's sessions, newest first."""

    @abstractmethod
    async def add(self, session: ExerciseSession) -> ExerciseSession:
        """Persist a new session."""

    @abstractmethod
    async def update(self, session: ExerciseSession) -> ExerciseSession:
        """Persist changes to an active session."""

    @abstractmethod
    async def add_results(self, results: tuple[ExerciseResult, ...]) -> int:
        """Append detector output to a session.

        Results are immutable, so they are only ever appended.

        Returns:
            The number of results written.
        """

    @abstractmethod
    async def list_results(self, session_id: UUID) -> tuple[ExerciseResult, ...]:
        """Return the detector output captured during a session."""
