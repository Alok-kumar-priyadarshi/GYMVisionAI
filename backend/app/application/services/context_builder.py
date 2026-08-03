# file_name: context_builder.py

"""The Context Builder.

Implements ``contexts/09_CONTEXT_BUILDER_RULES.md``: it retrieves only the
context the current intent needs, assembles exactly one Context Package, and
preserves deterministic ordering.

Per ``instructions/04_AI_RULES.md`` section 4 it never builds prompts, never
calls a provider and never performs business logic. It lives in the application
layer because it reads repositories, which the AI engine may not.
"""

import logging
from uuid import UUID

from app.domain.entities.user import User
from app.domain.repositories.exercise_repository import (
    ExerciseRepository,
    ExerciseSessionRepository,
)
from app.domain.repositories.progress_repository import ProgressRepository
from app.domain.repositories.user_repository import BodyProfileRepository
from app.domain.repositories.workout_repository import WorkoutPlanRepository
from app.domain.value_objects.enums import FitnessGoal, SessionStatus
from app.engines.ai.context_package import (
    ApplicationContext,
    ContextPackage,
    ConversationContext,
    ExerciseContext,
    Intent,
    Message,
    ProgressContext,
    SessionSummaryContext,
    UserContext,
    WorkoutContext,
)
from app.engines.ai.conversation_memory import (
    DEFAULT_WINDOW_MESSAGES,
    ConversationMemory,
)
from app.engines.exercise.catalog import load_exercise_registry
from app.shared.exceptions import ExerciseNotFoundError, WorkoutNotFoundError

logger = logging.getLogger(__name__)

RECENT_SESSION_LIMIT = 8
"""Sessions summarised for a workout review.

Enough to characterise a workout without inflating the prompt, which section 7
of the AI Architecture warns against.
"""

CAPABILITIES = (
    "Real-time posture analysis and repetition counting through the device camera",
    "Deterministic workout generation from the user's profile",
    "Deterministic daily diet planning",
    "Progress tracking with streaks",
    "Exercise explanations and completed-workout reviews",
)
"""What the product actually does, so the assistant cannot invent features."""


class ContextBuilder:
    """Gathers the context one AI request needs."""

    def __init__(
        self,
        profiles: BodyProfileRepository,
        plans: WorkoutPlanRepository,
        exercises: ExerciseRepository,
        sessions: ExerciseSessionRepository,
        progress: ProgressRepository,
        memory: ConversationMemory,
    ) -> None:
        self._profiles = profiles
        self._plans = plans
        self._exercises = exercises
        self._sessions = sessions
        self._progress = progress
        self._memory = memory

    async def build_chat_context(
        self, user: User, conversation_id: str
    ) -> ContextPackage:
        """Assemble context for a conversational request."""
        return ContextPackage(
            intent=Intent.CHAT,
            user=await self._user_context(user),
            workout=await self._workout_context(user.id),
            progress=await self._progress_context(user.id),
            conversation=self._conversation_context(conversation_id, user.id),
            application=self._application_context(),
        )

    async def build_exercise_context(self, user: User, slug: str) -> ContextPackage:
        """Assemble context for an exercise explanation.

        Raises:
            ExerciseNotFoundError: If the exercise is not in the library.
        """
        exercise = await self._exercises.get_by_slug(slug)
        if exercise is None:
            raise ExerciseNotFoundError(f"Exercise '{slug}' not found.")

        return ContextPackage(
            intent=Intent.EXPLAIN_EXERCISE,
            user=await self._user_context(user),
            exercise=ExerciseContext(
                slug=exercise.slug,
                name=exercise.name,
                category=str(exercise.category),
                difficulty=str(exercise.difficulty),
                exercise_type=str(exercise.exercise_type),
                equipment=tuple(str(item) for item in exercise.equipment),
                primary_muscles=exercise.primary_muscles,
                secondary_muscles=exercise.secondary_muscles,
                instructions=exercise.instructions,
            ),
            application=self._application_context(),
        )

    async def build_review_context(
        self, user: User, workout_id: UUID
    ) -> ContextPackage:
        """Assemble context for a completed-workout review.

        Raises:
            WorkoutNotFoundError: If the workout does not exist or belongs to
                another user.
        """
        plan = await self._plans.get(workout_id)
        if plan is None or plan.user_id != user.id:
            raise WorkoutNotFoundError()

        return ContextPackage(
            intent=Intent.REVIEW_WORKOUT,
            user=await self._user_context(user),
            workout=await self._plan_context(plan),
            sessions=await self._session_summaries(user.id),
            progress=await self._progress_context(user.id),
            application=self._application_context(),
        )

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    async def _user_context(self, user: User) -> UserContext:
        """Summarise who the user is."""
        profile = await self._profiles.get_for_user(user.id)
        if profile is None:
            return UserContext(name=user.full_name)

        return UserContext(
            name=user.full_name,
            goal=str(profile.fitness_goal),
            fitness_level=str(profile.fitness_level),
            age=profile.age,
            workout_duration_minutes=profile.workout_duration_minutes,
            problem_areas=profile.problem_areas,
        )

    async def _workout_context(self, user_id: UUID) -> WorkoutContext | None:
        """Summarise the user's current plan, if they have one."""
        plan = await self._plans.get_current_for_user(user_id)
        return await self._plan_context(plan) if plan else None

    async def _plan_context(self, plan) -> WorkoutContext:
        """Summarise one plan, resolving its exercise names."""
        names = []
        for prescribed in plan.in_order():
            exercise = await self._exercises.get(prescribed.exercise_id)
            if exercise is not None:
                names.append(exercise.name)

        return WorkoutContext(
            title=plan.title,
            goal=str(plan.goal),
            difficulty=str(plan.difficulty),
            estimated_duration_minutes=plan.estimated_duration_minutes,
            exercise_names=tuple(names),
        )

    async def _session_summaries(
        self, user_id: UUID
    ) -> tuple[SessionSummaryContext, ...]:
        """Summarise recent completed sessions.

        Detector output reaches the AI only in this summarised form, per
        ``docs/08_ai/41_AI_ARCHITECTURE.md`` section 11.
        """
        sessions = await self._sessions.list_for_user(
            user_id, limit=RECENT_SESSION_LIMIT
        )

        summaries = []
        for session in sessions:
            if session.status is not SessionStatus.COMPLETED:
                continue

            exercise = await self._exercises.get(session.exercise_id)
            results = await self._sessions.list_results(session.id)

            feedback: list[str] = []
            for result in results:
                for note in result.feedback:
                    if note not in feedback:
                        feedback.append(note)

            summaries.append(
                SessionSummaryContext(
                    exercise_name=exercise.name if exercise else "Unknown exercise",
                    repetitions=session.total_reps,
                    duration_seconds=session.duration_seconds,
                    average_accuracy=(
                        round(session.average_accuracy * 100)
                        if session.average_accuracy is not None
                        else None
                    ),
                    common_feedback=tuple(feedback[:4]),
                )
            )

        return tuple(summaries)

    async def _progress_context(self, user_id: UUID) -> ProgressContext | None:
        """Summarise long-term progress, if any is recorded."""
        progress = await self._progress.get_for_user(user_id)
        if progress is None or progress.total_workouts == 0:
            return None

        return ProgressContext(
            current_streak=progress.current_streak,
            longest_streak=progress.longest_streak,
            total_workouts=progress.total_workouts,
            total_minutes=progress.total_minutes,
        )

    def _conversation_context(
        self, conversation_id: str, user_id: UUID
    ) -> ConversationContext:
        """Return the recent turns of the active conversation."""
        window = self._memory.window(
            conversation_id, user_id, limit=DEFAULT_WINDOW_MESSAGES
        )
        return ConversationContext(
            conversation_id=conversation_id,
            messages=tuple(
                Message(role=item.role, content=item.content) for item in window
            ),
        )

    @staticmethod
    def _application_context() -> ApplicationContext:
        """Describe what the product can do."""
        return ApplicationContext(
            supported_exercise_count=len(load_exercise_registry()),
            supported_goals=tuple(str(goal) for goal in FitnessGoal),
            capabilities=CAPABILITIES,
        )
