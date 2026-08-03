# file_name: dependencies.py

"""FastAPI dependency wiring.

``instructions/02_BACKEND_RULES.md`` section 8 requires dependency injection for
sessions, authentication, configuration, services and providers, and forbids
global mutable state. Every dependency here is request-scoped.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.ai_service import AIService
from app.application.services.auth_service import AuthService
from app.application.services.diet_service import DietService
from app.application.services.context_builder import ContextBuilder
from app.core.config import Settings, get_settings
from app.core.security import TokenService, TokenType
from app.engines.ai.conversation_memory import (
    ConversationMemory,
    InMemoryConversationMemory,
)
from app.engines.ai.prompt_builder import PromptBuilder, build_prompt_builder
from app.engines.ai.provider import AIProvider, GroqProvider
from app.engines.ai.response_validator import ResponseValidator
from app.domain.entities.user import User
from app.infrastructure.auth.google_identity import (
    GoogleIdentityProvider,
    GoogleOAuthIdentityProvider,
)
from app.infrastructure.database.session import get_session
from app.infrastructure.repositories.diet_repository import (
    SqlDietPlanRepository,
    SqlFoodRepository,
)
from app.infrastructure.repositories.exercise_repository import (
    SqlExerciseRepository,
    SqlExerciseSessionRepository,
)
from app.infrastructure.repositories.progress_repository import SqlProgressRepository
from app.infrastructure.repositories.user_repository import (
    SqlBodyProfileRepository,
    SqlUserRepository,
)
from app.infrastructure.repositories.workout_repository import (
    SqlWorkoutPlanRepository,
    SqlWorkoutSessionRepository,
)
from app.shared.exceptions import AuthenticationError, InvalidTokenError

logger = logging.getLogger(__name__)

BEARER_PREFIX = "bearer"

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------


def get_user_repository(session: SessionDep) -> SqlUserRepository:
    """Provide the user repository."""
    return SqlUserRepository(session)


def get_body_profile_repository(session: SessionDep) -> SqlBodyProfileRepository:
    """Provide the body profile repository."""
    return SqlBodyProfileRepository(session)


def get_exercise_repository(session: SessionDep) -> SqlExerciseRepository:
    """Provide the exercise repository."""
    return SqlExerciseRepository(session)


def get_exercise_session_repository(
    session: SessionDep,
) -> SqlExerciseSessionRepository:
    """Provide the exercise session repository."""
    return SqlExerciseSessionRepository(session)


def get_workout_plan_repository(session: SessionDep) -> SqlWorkoutPlanRepository:
    """Provide the workout plan repository."""
    return SqlWorkoutPlanRepository(session)


def get_workout_session_repository(session: SessionDep) -> SqlWorkoutSessionRepository:
    """Provide the workout session repository."""
    return SqlWorkoutSessionRepository(session)


def get_food_repository(session: SessionDep) -> SqlFoodRepository:
    """Provide the food repository."""
    return SqlFoodRepository(session)


def get_diet_plan_repository(session: SessionDep) -> SqlDietPlanRepository:
    """Provide the diet plan repository."""
    return SqlDietPlanRepository(session)


def get_progress_repository(session: SessionDep) -> SqlProgressRepository:
    """Provide the progress repository."""
    return SqlProgressRepository(session)


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


def get_token_service(settings: SettingsDep) -> TokenService:
    """Provide the token service."""
    return TokenService(settings)


def get_diet_service(
    plans: Annotated[SqlDietPlanRepository, Depends(get_diet_plan_repository)],
    foods: Annotated[SqlFoodRepository, Depends(get_food_repository)],
    profiles: Annotated[SqlBodyProfileRepository, Depends(get_body_profile_repository)],
) -> DietService:
    """Provide the diet plan service."""
    return DietService(plans, foods, profiles)


def get_identity_provider(settings: SettingsDep) -> GoogleIdentityProvider:
    """Provide the Google identity provider."""
    return GoogleOAuthIdentityProvider(settings)


def get_auth_service(
    users: Annotated[SqlUserRepository, Depends(get_user_repository)],
    progress: Annotated[SqlProgressRepository, Depends(get_progress_repository)],
    identity: Annotated[GoogleIdentityProvider, Depends(get_identity_provider)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> AuthService:
    """Provide the authentication service."""
    return AuthService(users, progress, identity, tokens)


def _bearer_token(request: Request) -> str:
    """Extract the bearer token from the Authorization header.

    Raises:
        AuthenticationError: If the header is missing or not a bearer scheme.
    """
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")

    if scheme.lower() != BEARER_PREFIX or not token.strip():
        raise AuthenticationError()
    return token.strip()


def get_current_user_id(
    request: Request,
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> UUID:
    """Return the authenticated user's identifier.

    Raises:
        AuthenticationError: If no bearer token is supplied.
        InvalidTokenError: If the token is not a valid access token.
        ExpiredTokenError: If the token has expired.
    """
    return tokens.verify(_bearer_token(request), TokenType.ACCESS).subject


async def get_current_user(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    users: Annotated[SqlUserRepository, Depends(get_user_repository)],
) -> User:
    """Return the authenticated user.

    Raises:
        InvalidTokenError: If the token names a user that no longer exists. The
            token is well-formed but no longer usable, and the client should
            re-authenticate rather than be told which accounts exist.
    """
    user = await users.get(user_id)
    if user is None:
        logger.warning("Token presented for a user that no longer exists.")
        raise InvalidTokenError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# AI subsystem
# ---------------------------------------------------------------------------

_conversation_memory: ConversationMemory = InMemoryConversationMemory()
"""Process-wide conversation store.

The domain model defines no Conversation entity, so there is nowhere to persist
to. Held here so the instance is shared across requests; conversations are lost
on restart. Recorded in PROJECT_STATUS.
"""

_prompt_builder: PromptBuilder | None = None


def get_conversation_memory() -> ConversationMemory:
    """Provide the conversation memory."""
    return _conversation_memory


def get_prompt_builder() -> PromptBuilder:
    """Provide the prompt builder, loading templates once."""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = build_prompt_builder()
    return _prompt_builder


def get_ai_provider(settings: SettingsDep) -> AIProvider:
    """Provide the configured language model provider."""
    return GroqProvider(
        api_key=(
            settings.groq_api_key.get_secret_value()
            if settings.groq_api_key is not None
            else None
        ),
        model=settings.ai_model,
    )


def get_response_validator() -> ResponseValidator:
    """Provide the response validator."""
    return ResponseValidator()


def get_context_builder(
    profiles: Annotated[SqlBodyProfileRepository, Depends(get_body_profile_repository)],
    plans: Annotated[SqlWorkoutPlanRepository, Depends(get_workout_plan_repository)],
    exercises: Annotated[SqlExerciseRepository, Depends(get_exercise_repository)],
    sessions: Annotated[
        SqlExerciseSessionRepository, Depends(get_exercise_session_repository)
    ],
    progress: Annotated[SqlProgressRepository, Depends(get_progress_repository)],
    memory: Annotated[ConversationMemory, Depends(get_conversation_memory)],
) -> ContextBuilder:
    """Provide the context builder."""
    return ContextBuilder(profiles, plans, exercises, sessions, progress, memory)


def get_ai_service(
    settings: SettingsDep,
    context: Annotated[ContextBuilder, Depends(get_context_builder)],
    prompts: Annotated[PromptBuilder, Depends(get_prompt_builder)],
    provider: Annotated[AIProvider, Depends(get_ai_provider)],
    validator: Annotated[ResponseValidator, Depends(get_response_validator)],
    memory: Annotated[ConversationMemory, Depends(get_conversation_memory)],
) -> AIService:
    """Provide the AI service."""
    return AIService(
        context_builder=context,
        prompt_builder=prompts,
        provider=provider,
        validator=validator,
        memory=memory,
        temperature=settings.ai_temperature,
        max_tokens=settings.ai_max_tokens,
        timeout_seconds=settings.ai_timeout_seconds,
    )
