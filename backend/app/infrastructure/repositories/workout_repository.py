# file_name: workout_repository.py

"""SQLAlchemy implementations of the workout repositories."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.workout import WorkoutPlan, WorkoutSession
from app.domain.repositories.workout_repository import (
    WorkoutPlanRepository,
    WorkoutSessionRepository,
)
from app.domain.value_objects.enums import SessionStatus, WorkoutPlanStatus
from app.infrastructure.database import mappers
from app.infrastructure.database.models import WorkoutPlanModel, WorkoutSessionModel

ACTIVE_STATUSES = (
    str(SessionStatus.CREATED),
    str(SessionStatus.RUNNING),
    str(SessionStatus.PAUSED),
)


class SqlWorkoutPlanRepository(WorkoutPlanRepository):
    """Stores workout plans and their exercises in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, plan_id: UUID) -> WorkoutPlan | None:
        model = await self._session.get(WorkoutPlanModel, plan_id)
        return mappers.to_workout_plan(model) if model else None

    async def get_current_for_user(self, user_id: UUID) -> WorkoutPlan | None:
        result = await self._session.execute(
            select(WorkoutPlanModel)
            .where(
                WorkoutPlanModel.user_id == user_id,
                WorkoutPlanModel.status != str(WorkoutPlanStatus.ARCHIVED),
            )
            .order_by(WorkoutPlanModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return mappers.to_workout_plan(model) if model else None

    async def list_for_user(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> tuple[WorkoutPlan, ...]:
        result = await self._session.execute(
            select(WorkoutPlanModel)
            .where(WorkoutPlanModel.user_id == user_id)
            .order_by(WorkoutPlanModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return tuple(mappers.to_workout_plan(model) for model in result.scalars())

    async def count_for_user(self, user_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(WorkoutPlanModel)
            .where(WorkoutPlanModel.user_id == user_id)
        )
        return int(result.scalar_one())

    async def add(self, plan: WorkoutPlan) -> WorkoutPlan:
        """Persist a plan and its exercises.

        The child rows cascade from the parent, so the whole plan is written in
        one transaction and a failure leaves nothing behind.
        """
        model = mappers.to_workout_plan_model(plan)
        self._session.add(model)
        await self._session.flush()
        return mappers.to_workout_plan(model)

    async def archive(self, plan_id: UUID) -> None:
        model = await self._session.get(WorkoutPlanModel, plan_id)
        if model is not None:
            model.status = str(WorkoutPlanStatus.ARCHIVED)
            await self._session.flush()

    async def delete(self, plan_id: UUID) -> None:
        await self._session.execute(
            delete(WorkoutPlanModel).where(WorkoutPlanModel.id == plan_id)
        )
        await self._session.flush()


class SqlWorkoutSessionRepository(WorkoutSessionRepository):
    """Stores workout sessions in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, session_id: UUID) -> WorkoutSession | None:
        model = await self._session.get(WorkoutSessionModel, session_id)
        return mappers.to_workout_session(model) if model else None

    async def get_active_for_user(self, user_id: UUID) -> WorkoutSession | None:
        result = await self._session.execute(
            select(WorkoutSessionModel)
            .where(
                WorkoutSessionModel.user_id == user_id,
                WorkoutSessionModel.status.in_(ACTIVE_STATUSES),
            )
            .order_by(WorkoutSessionModel.started_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return mappers.to_workout_session(model) if model else None

    async def list_for_user(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> tuple[WorkoutSession, ...]:
        result = await self._session.execute(
            select(WorkoutSessionModel)
            .where(WorkoutSessionModel.user_id == user_id)
            .order_by(WorkoutSessionModel.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return tuple(mappers.to_workout_session(model) for model in result.scalars())

    async def add(self, session: WorkoutSession) -> WorkoutSession:
        model = mappers.to_workout_session_model(session)
        self._session.add(model)
        await self._session.flush()
        return mappers.to_workout_session(model)

    async def update(self, session: WorkoutSession) -> WorkoutSession:
        model = await self._session.get(WorkoutSessionModel, session.id)
        if model is None:
            raise ValueError(f"workout session {session.id} does not exist")

        mappers.apply_workout_session(model, session)
        await self._session.flush()
        return mappers.to_workout_session(model)
