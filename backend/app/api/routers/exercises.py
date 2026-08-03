# file_name: exercises.py

"""Exercise endpoints.

Implements ``contracts/exercises/01_START_SESSION.md`` through
``contracts/exercises/07_GET_HISTORY.md``.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.application.services.exercise_service import ExerciseService, LiveSession
from app.core.dependencies import (
    CurrentUser,
    get_exercise_repository,
    get_exercise_session_repository,
)
from app.domain.entities.exercise import Exercise, ExerciseSession
from app.engines.exercise.detector_registry import DetectorRegistry
from app.infrastructure.repositories.exercise_repository import (
    SqlExerciseRepository,
    SqlExerciseSessionRepository,
)
from app.schemas.dto import (
    EndSessionRequest,
    ExerciseDetailResponse,
    ExerciseSummaryResponse,
    FrameResponse,
    ProcessFrameRequest,
    SessionResponse,
    SessionSummaryResponse,
    StartSessionRequest,
)
from app.schemas.response import success
from app.shared.exceptions import ExerciseSessionNotFoundError

router = APIRouter()

_LIVE_SESSIONS: dict[UUID, LiveSession] = {}
"""Runtime detector state, keyed by session.

Held in the process because a detector is stateful across frames and must not be
rebuilt per request. This makes the frame endpoint sticky to one instance; a
shared store would be required before running several replicas.
"""


def get_exercise_service(
    exercises: Annotated[SqlExerciseRepository, Depends(get_exercise_repository)],
    sessions: Annotated[
        SqlExerciseSessionRepository, Depends(get_exercise_session_repository)
    ],
) -> ExerciseService:
    """Provide the exercise service."""
    return ExerciseService(exercises, sessions, _LIVE_SESSIONS)


ServiceDep = Annotated[ExerciseService, Depends(get_exercise_service)]


def to_summary(exercise: Exercise) -> ExerciseSummaryResponse:
    """Shape an exercise for the library listing."""
    return ExerciseSummaryResponse(
        exercise_id=exercise.slug,
        name=exercise.name,
        category=str(exercise.category),
        difficulty=str(exercise.difficulty),
        exercise_type=str(exercise.exercise_type),
        detector_available=DetectorRegistry.is_supported(exercise.slug),
    )


def to_session_summary(session: ExerciseSession) -> SessionSummaryResponse:
    """Shape a finished session for the API."""
    return SessionSummaryResponse(
        session_id=str(session.id),
        exercise_id=str(session.exercise_id),
        status=str(session.status),
        total_reps=session.total_reps,
        duration_seconds=session.duration_seconds,
        average_accuracy=session.average_accuracy,
        started_at=session.started_at,
        completed_at=session.completed_at,
    )


@router.get("", summary="List every supported exercise")
async def list_exercises(user: CurrentUser, service: ServiceDep) -> dict[str, Any]:
    """Return the supported exercise library."""
    exercises = await service.list_exercises()

    return success(
        "Supported exercises retrieved successfully.",
        [to_summary(item).model_dump(by_alias=True) for item in exercises],
    )


@router.get("/history", summary="List the user's past exercise sessions")
async def get_history(
    user: CurrentUser,
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Return the signed-in user's session history."""
    sessions = await service.history(user.id, limit=limit, offset=offset)

    return success(
        "Exercise history retrieved successfully.",
        [to_session_summary(item).model_dump(by_alias=True) for item in sessions],
    )


@router.post(
    "/start",
    status_code=status.HTTP_201_CREATED,
    summary="Start a live exercise session",
)
async def start_session(
    payload: StartSessionRequest, user: CurrentUser, service: ServiceDep
) -> dict[str, Any]:
    """Initialise a detector and open a session."""
    session, exercise = await service.start(user.id, payload.exercise_id)

    return success(
        "Exercise session started successfully.",
        SessionResponse(
            session_id=str(session.id),
            workout_id=payload.workout_id,
            exercise_id=exercise.slug,
            exercise_name=exercise.name,
            status=str(session.status).lower(),
            started_at=session.started_at,
        ).model_dump(by_alias=True),
    )


@router.post("/frame", summary="Process one camera frame")
async def process_frame(
    payload: ProcessFrameRequest, user: CurrentUser, service: ServiceDep
) -> dict[str, Any]:
    """Analyse a frame of pose landmarks.

    Raw landmarks are never stored, per the contract's business rules.
    """
    try:
        session_id = UUID(payload.session_id)
    except ValueError as error:
        raise ExerciseSessionNotFoundError() from error

    result, exercise = await service.process_frame(
        user.id, session_id, payload.landmarks
    )

    return success(
        "Frame processed successfully.",
        FrameResponse(
            session_id=payload.session_id,
            exercise_id=exercise.slug,
            reps=result.reps,
            stage=result.stage,
            feedback=list(result.feedback),
            metrics=dict(result.metrics),
        ).model_dump(by_alias=True),
    )


@router.post("/end", summary="End a live exercise session")
async def end_session(
    payload: EndSessionRequest, user: CurrentUser, service: ServiceDep
) -> dict[str, Any]:
    """Close a session and return its totals."""
    try:
        session_id = UUID(payload.session_id)
    except ValueError as error:
        raise ExerciseSessionNotFoundError() from error

    session = await service.end(user.id, session_id)

    return success(
        "Exercise session ended successfully.",
        to_session_summary(session).model_dump(by_alias=True),
    )


@router.get("/sessions/{session_id}", summary="Get one exercise session")
async def get_session(
    session_id: UUID, user: CurrentUser, service: ServiceDep
) -> dict[str, Any]:
    """Return one of the signed-in user's sessions."""
    session = await service.get_session(user.id, session_id)

    return success(
        "Exercise session retrieved successfully.",
        to_session_summary(session).model_dump(by_alias=True),
    )


@router.get("/{slug}", summary="Get one exercise")
async def get_exercise(
    slug: str, user: CurrentUser, service: ServiceDep
) -> dict[str, Any]:
    """Return full metadata for one exercise."""
    exercise = await service.get_exercise(slug)

    return success(
        "Exercise retrieved successfully.",
        ExerciseDetailResponse(
            **to_summary(exercise).model_dump(),
            equipment=[str(item) for item in exercise.equipment],
            primary_muscles=list(exercise.primary_muscles),
            secondary_muscles=list(exercise.secondary_muscles),
            instructions=list(exercise.instructions),
            movement_type=str(exercise.movement_type),
        ).model_dump(by_alias=True),
    )
