# file_name: progress_repository.py

"""SQLAlchemy implementation of the progress repository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.progress import Progress
from app.domain.repositories.progress_repository import ProgressRepository
from app.infrastructure.database import mappers
from app.infrastructure.database.models import ProgressModel


class SqlProgressRepository(ProgressRepository):
    """Stores long-term user statistics in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, user_id: UUID) -> Progress | None:
        result = await self._session.execute(
            select(ProgressModel).where(ProgressModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        return mappers.to_progress(model) if model else None

    async def add(self, progress: Progress) -> Progress:
        model = mappers.to_progress_model(progress)
        self._session.add(model)
        await self._session.flush()
        return mappers.to_progress(model)

    async def update(self, progress: Progress) -> Progress:
        result = await self._session.execute(
            select(ProgressModel).where(ProgressModel.user_id == progress.user_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"progress for user {progress.user_id} does not exist")

        mappers.apply_progress(model, progress)
        await self._session.flush()
        return mappers.to_progress(model)
