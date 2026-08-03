# file_name: progress.py

"""Progress endpoints.

Implements ``contracts/progress/01_GET_PROGRESS.md`` through
``contracts/progress/03_GET_STATISTICS.md``.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.dependencies import (
    CurrentUser,
    get_body_profile_repository,
    get_exercise_session_repository,
    get_progress_repository,
    get_workout_plan_repository,
)
from app.domain.entities.progress import Progress
from app.domain.value_objects.enums import SessionStatus
from app.infrastructure.repositories.exercise_repository import (
    SqlExerciseSessionRepository,
)
from app.infrastructure.repositories.progress_repository import SqlProgressRepository
from app.infrastructure.repositories.user_repository import SqlBodyProfileRepository
from app.infrastructure.repositories.workout_repository import SqlWorkoutPlanRepository
from app.api.routers.auth import to_user_response
from app.api.routers.workouts import to_summary
from app.schemas.dto import DashboardResponse, ProgressResponse, StatisticsResponse
from app.schemas.response import success

router = APIRouter()

ProgressRepositoryDep = Annotated[
    SqlProgressRepository, Depends(get_progress_repository)
]
SessionRepositoryDep = Annotated[
    SqlExerciseSessionRepository, Depends(get_exercise_session_repository)
]
PlanRepositoryDep = Annotated[
    SqlWorkoutPlanRepository, Depends(get_workout_plan_repository)
]
ProfileRepositoryDep = Annotated[
    SqlBodyProfileRepository, Depends(get_body_profile_repository)
]

HISTORY_SAMPLE_LIMIT = 500
"""How many sessions the statistics endpoint aggregates over."""


def to_progress_response(progress: Progress) -> ProgressResponse:
    """Shape progress for the API."""
    return ProgressResponse(
        current_streak=progress.current_streak,
        longest_streak=progress.longest_streak,
        total_workouts=progress.total_workouts,
        total_exercises=progress.total_exercises,
        total_minutes=progress.total_minutes,
        average_workout_minutes=progress.average_workout_minutes,
        last_workout_date=(
            progress.last_workout_date.isoformat()
            if progress.last_workout_date
            else None
        ),
    )


async def load_progress(user_id, repository: SqlProgressRepository) -> Progress:
    """Return a user's progress, defaulting to an empty record.

    A user who has never trained has no stored row. Returning an empty record is
    correct and keeps the endpoint free of a "not found" case for a resource the
    user always conceptually owns.
    """
    stored = await repository.get_for_user(user_id)
    return stored or Progress(user_id=user_id)


@router.get("", summary="Get the user's progress")
async def get_progress(
    user: CurrentUser, progress: ProgressRepositoryDep
) -> dict[str, Any]:
    """Return streaks and lifetime totals."""
    record = await load_progress(user.id, progress)

    return success(
        "Progress retrieved successfully.",
        to_progress_response(record).model_dump(by_alias=True),
    )


@router.get("/dashboard", summary="Get the dashboard summary")
async def get_dashboard(
    user: CurrentUser,
    progress: ProgressRepositoryDep,
    plans: PlanRepositoryDep,
    profiles: ProfileRepositoryDep,
) -> dict[str, Any]:
    """Return everything the dashboard shows in one request."""
    record = await load_progress(user.id, progress)
    current = await plans.get_current_for_user(user.id)
    profile = await profiles.get_for_user(user.id)

    return success(
        "Dashboard retrieved successfully.",
        DashboardResponse(
            user=to_user_response(user),
            progress=to_progress_response(record),
            current_workout=to_summary(current) if current else None,
            has_profile=profile is not None,
        ).model_dump(by_alias=True),
    )


@router.get("/statistics", summary="Get aggregated training statistics")
async def get_statistics(
    user: CurrentUser,
    progress: ProgressRepositoryDep,
    sessions: SessionRepositoryDep,
) -> dict[str, Any]:
    """Return lifetime totals alongside exercise session aggregates."""
    record = await load_progress(user.id, progress)
    history = await sessions.list_for_user(user.id, limit=HISTORY_SAMPLE_LIMIT)

    completed = [
        item for item in history if item.status is SessionStatus.COMPLETED
    ]

    return success(
        "Statistics retrieved successfully.",
        StatisticsResponse(
            total_workouts=record.total_workouts,
            total_exercises=record.total_exercises,
            total_minutes=record.total_minutes,
            average_workout_minutes=record.average_workout_minutes,
            completed_sessions=len(completed),
            total_reps=sum(item.total_reps for item in completed),
        ).model_dump(by_alias=True),
    )
