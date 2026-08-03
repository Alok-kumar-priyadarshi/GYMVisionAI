# file_name: workout_repository.py

"""Repository interfaces for the workout domain."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.workout import WorkoutPlan, WorkoutSession


class WorkoutPlanRepository(ABC):
    """Persistence for the ``WorkoutPlan`` aggregate.

    A plan is immutable after generation, so there is no update method. A
    changed plan is a new plan, which keeps completed history truthful.
    """

    @abstractmethod
    async def get(self, plan_id: UUID) -> WorkoutPlan | None:
        """Return a plan by identifier, or ``None`` if absent."""

    @abstractmethod
    async def get_current_for_user(self, user_id: UUID) -> WorkoutPlan | None:
        """Return a user's most recent unarchived plan."""

    @abstractmethod
    async def list_for_user(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> tuple[WorkoutPlan, ...]:
        """Return a user's plans, newest first."""

    @abstractmethod
    async def count_for_user(self, user_id: UUID) -> int:
        """Return how many plans a user owns, for pagination."""

    @abstractmethod
    async def add(self, plan: WorkoutPlan) -> WorkoutPlan:
        """Persist a new plan and its exercises in one transaction."""

    @abstractmethod
    async def archive(self, plan_id: UUID) -> None:
        """Retire a plan without deleting it."""

    @abstractmethod
    async def delete(self, plan_id: UUID) -> None:
        """Remove a plan, per ``contracts/workouts/05_DELETE_WORKOUT.md``."""


class WorkoutSessionRepository(ABC):
    """Persistence for the ``WorkoutSession`` aggregate."""

    @abstractmethod
    async def get(self, session_id: UUID) -> WorkoutSession | None:
        """Return a session by identifier, or ``None`` if absent."""

    @abstractmethod
    async def get_active_for_user(self, user_id: UUID) -> WorkoutSession | None:
        """Return a user's running session, or ``None`` if none is active."""

    @abstractmethod
    async def list_for_user(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> tuple[WorkoutSession, ...]:
        """Return a user's sessions, newest first."""

    @abstractmethod
    async def add(self, session: WorkoutSession) -> WorkoutSession:
        """Persist a new session."""

    @abstractmethod
    async def update(self, session: WorkoutSession) -> WorkoutSession:
        """Persist changes to an active session."""
