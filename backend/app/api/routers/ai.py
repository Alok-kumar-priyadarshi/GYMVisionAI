# file_name: ai.py

"""AI assistant endpoints.

Implements ``contracts/ai/01_CHAT.md``, ``02_EXPLAIN_EXERCISE.md`` and
``03_REVIEW_WORKOUT.md``.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from app.application.services.ai_service import AIService
from app.core.dependencies import CurrentUser, get_ai_service
from app.schemas.dto import (
    ChatRequest,
    ChatResponse,
    ExplainExerciseRequest,
    ExerciseExplanationResponse,
    ReviewWorkoutRequest,
    WorkoutReviewResponse,
)
from app.schemas.response import success
from app.shared.exceptions import WorkoutNotFoundError

router = APIRouter()

ServiceDep = Annotated[AIService, Depends(get_ai_service)]


@router.post("/chat", summary="Send a message to the AI assistant")
async def chat(
    payload: ChatRequest, user: CurrentUser, service: ServiceDep
) -> dict[str, Any]:
    """Answer a conversational message."""
    answer = await service.chat(user, payload.conversation_id, payload.message)

    return success(
        "AI response generated successfully.",
        ChatResponse(
            conversation_id=answer.conversation_id,
            response=answer.response,
            created_at=answer.created_at,
        ).model_dump(by_alias=True),
    )


@router.post("/explain", summary="Explain a supported exercise")
async def explain_exercise(
    payload: ExplainExerciseRequest, user: CurrentUser, service: ServiceDep
) -> dict[str, Any]:
    """Return an educational explanation of one exercise."""
    explanation = await service.explain_exercise(user, payload.exercise_id)

    return success(
        "Exercise explanation generated successfully.",
        ExerciseExplanationResponse(
            exercise_id=explanation.exercise_id,
            title=explanation.title,
            explanation=explanation.explanation,
        ).model_dump(by_alias=True),
    )


@router.post("/review", summary="Review a completed workout")
async def review_workout(
    payload: ReviewWorkoutRequest, user: CurrentUser, service: ServiceDep
) -> dict[str, Any]:
    """Return coaching feedback on a completed workout."""
    try:
        workout_id = UUID(payload.workout_id)
    except ValueError as error:
        raise WorkoutNotFoundError() from error

    review = await service.review_workout(user, workout_id)

    return success(
        "Workout review generated successfully.",
        WorkoutReviewResponse(
            workout_id=review.workout_id,
            summary=review.summary,
            strengths=list(review.strengths),
            improvements=list(review.improvements),
            motivation=review.motivation,
        ).model_dump(by_alias=True),
    )
