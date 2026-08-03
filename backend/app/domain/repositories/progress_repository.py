# file_name: progress_repository.py

"""Repository interface for the progress domain."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.progress import Progress


class ProgressRepository(ABC):
    """Persistence for the ``Progress`` aggregate.

    Every user owns exactly one progress record, so it is fetched by user rather
    than by its own identifier.
    """

    @abstractmethod
    async def get_for_user(self, user_id: UUID) -> Progress | None:
        """Return a user's progress, or ``None`` if nothing is recorded yet."""

    @abstractmethod
    async def add(self, progress: Progress) -> Progress:
        """Create a user's progress record."""

    @abstractmethod
    async def update(self, progress: Progress) -> Progress:
        """Persist recalculated progress.

        Called only after a workout completes, per the business rules in
        ``docs/04_backend/29_DOMAIN_MODEL.md`` section 8.
        """
