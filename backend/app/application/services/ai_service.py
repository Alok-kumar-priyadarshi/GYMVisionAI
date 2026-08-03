# file_name: ai_service.py

"""The AI service.

Coordinates the pipeline mandated by ``instructions/04_AI_RULES.md`` section 2:

    intent -> context builder -> prompt builder -> provider -> validation

Per section 7 it coordinates only. It does not build context, does not construct
prompts, and never touches a provider SDK.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.user import User, utc_now
from app.engines.ai.context_package import ContextPackage
from app.engines.ai.conversation_memory import (
    ASSISTANT_ROLE,
    USER_ROLE,
    ConversationMemory,
)
from app.engines.ai.prompt_builder import PromptBuilder
from app.engines.ai.provider import AIProvider, ProviderRequest
from app.engines.ai.response_validator import ResponseValidator
from app.application.services.context_builder import ContextBuilder
from app.core.logging_config import get_request_id
from app.shared.exceptions import AIProviderError, AIResponseError, AITimeoutError

logger = logging.getLogger(__name__)

REVIEW_KEYS = ("summary", "strengths", "improvements", "motivation")
MAX_LIST_ITEMS = 5


@dataclass(frozen=True, slots=True)
class ChatAnswer:
    """A conversational reply."""

    conversation_id: str
    response: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ExerciseExplanation:
    """An explanation of one exercise."""

    exercise_id: str
    title: str
    explanation: str


@dataclass(frozen=True, slots=True)
class WorkoutReview:
    """Coaching feedback on a completed workout."""

    workout_id: str
    summary: str
    strengths: tuple[str, ...]
    improvements: tuple[str, ...]
    motivation: str


class AIService:
    """Runs the AI pipeline for each supported request type."""

    def __init__(
        self,
        context_builder: ContextBuilder,
        prompt_builder: PromptBuilder,
        provider: AIProvider,
        validator: ResponseValidator,
        memory: ConversationMemory,
        temperature: float = 0.4,
        max_tokens: int = 800,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._context = context_builder
        self._prompts = prompt_builder
        self._provider = provider
        self._validator = validator
        self._memory = memory
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds

    async def chat(
        self, user: User, conversation_id: str, message: str
    ) -> ChatAnswer:
        """Answer a conversational message.

        The user's turn is recorded before generation so it appears in the
        window of the next request, and the reply is recorded only once it has
        passed validation.

        Raises:
            AIProviderError: If the provider is unavailable.
            AITimeoutError: If the provider does not respond in time.
            AIResponseError: If the reply fails validation.
        """
        package = await self._context.build_chat_context(user, conversation_id)
        content = await self._run(package, request=message)
        answer = self._validator.validate_text(content)

        self._memory.append(conversation_id, user.id, USER_ROLE, message)
        self._memory.append(conversation_id, user.id, ASSISTANT_ROLE, answer)

        return ChatAnswer(
            conversation_id=conversation_id, response=answer, created_at=utc_now()
        )

    async def explain_exercise(self, user: User, slug: str) -> ExerciseExplanation:
        """Explain one supported exercise.

        Raises:
            ExerciseNotFoundError: If the exercise is not in the library.
        """
        package = await self._context.build_exercise_context(user, slug)
        content = await self._run(package)

        return ExerciseExplanation(
            exercise_id=slug,
            title=package.exercise.name,
            explanation=self._validator.validate_text(content),
        )

    async def review_workout(self, user: User, workout_id: UUID) -> WorkoutReview:
        """Review a completed workout.

        Raises:
            WorkoutNotFoundError: If the workout does not belong to the user.
            AIResponseError: If the reply is not the documented JSON shape.
        """
        package = await self._context.build_review_context(user, workout_id)
        content = await self._run(package)
        payload = self._validator.validate_json(content, REVIEW_KEYS)

        return WorkoutReview(
            workout_id=str(workout_id),
            summary=str(payload["summary"]).strip(),
            strengths=self._string_list(payload["strengths"]),
            improvements=self._string_list(payload["improvements"]),
            motivation=str(payload["motivation"]).strip(),
        )

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    async def _run(self, package: ContextPackage, request: str = "") -> str:
        """Build the prompt, call the provider, and return the raw content."""
        prompt = self._prompts.build(package, request=request)
        started = time.perf_counter()

        try:
            response = await self._provider.generate(
                ProviderRequest(
                    system_prompt=prompt.system,
                    user_prompt=prompt.user,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                    timeout_seconds=self._timeout,
                    request_id=get_request_id(),
                )
            )
        except (AIProviderError, AITimeoutError):
            # Already logged by the adapter; re-raised for the API layer.
            raise

        # Operational metadata only: never the prompt or the response body.
        logger.info(
            "AI request completed: intent=%s provider=%s model=%s tokens=%s duration_ms=%d",
            package.intent,
            response.provider,
            response.model,
            response.total_tokens,
            round((time.perf_counter() - started) * 1000),
        )

        if response.finish_reason == "length":
            logger.warning("AI response was truncated by the token limit.")

        return response.content

    @staticmethod
    def _string_list(value: object) -> tuple[str, ...]:
        """Coerce a JSON list into clean strings.

        Raises:
            AIResponseError: If the value is not a list of usable strings.
        """
        if not isinstance(value, list):
            raise AIResponseError()

        items = [str(item).strip() for item in value if str(item).strip()]
        if not items:
            raise AIResponseError()
        return tuple(items[:MAX_LIST_ITEMS])
