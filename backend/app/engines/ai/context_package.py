# file_name: context_package.py

"""The Context Package.

Defined by ``contexts/08_CONTEXT_PACKAGE.md``: the single object the Context
Builder produces and the only thing the Prompt Builder consumes. Section 2
requires it to be immutable after construction, and section 5 makes every
section optional so only retrieved context is carried.

Nothing here retrieves data, builds prompts or calls a provider.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Intent(StrEnum):
    """What the user is asking for.

    Produced by the Intent Classifier and used to decide which context sections
    are worth retrieving, per ``instructions/04_AI_RULES.md`` section 3.
    """

    CHAT = "chat"
    EXPLAIN_EXERCISE = "explain_exercise"
    REVIEW_WORKOUT = "review_workout"


@dataclass(frozen=True, slots=True)
class UserContext:
    """Who the user is and what they are training for."""

    name: str
    goal: str | None = None
    fitness_level: str | None = None
    age: int | None = None
    workout_duration_minutes: int | None = None
    problem_areas: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExerciseContext:
    """Metadata for the exercise under discussion."""

    slug: str
    name: str
    category: str
    difficulty: str
    exercise_type: str
    equipment: tuple[str, ...] = ()
    primary_muscles: tuple[str, ...] = ()
    secondary_muscles: tuple[str, ...] = ()
    instructions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkoutContext:
    """The user's current plan."""

    title: str
    goal: str
    difficulty: str
    estimated_duration_minutes: int
    exercise_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SessionSummaryContext:
    """A summarised exercise session.

    ``docs/08_ai/41_AI_ARCHITECTURE.md`` section 11 requires detector output to
    reach the AI as a summary. Raw landmarks never appear here.
    """

    exercise_name: str
    repetitions: int
    duration_seconds: int
    average_accuracy: int | None = None
    common_feedback: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProgressContext:
    """The user's long-term statistics."""

    current_streak: int
    longest_streak: int
    total_workouts: int
    total_minutes: int


@dataclass(frozen=True, slots=True)
class Message:
    """One turn of a conversation."""

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ConversationContext:
    """The recent turns of the active conversation."""

    conversation_id: str
    messages: tuple[Message, ...] = ()


@dataclass(frozen=True, slots=True)
class ApplicationContext:
    """What the product can actually do.

    Grounds the assistant so it cannot invent features, per
    ``docs/08_ai/41_AI_ARCHITECTURE.md`` section 13.
    """

    supported_exercise_count: int
    supported_goals: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContextPackage:
    """Everything the Prompt Builder is allowed to see for one request."""

    intent: Intent
    user: UserContext | None = None
    exercise: ExerciseContext | None = None
    workout: WorkoutContext | None = None
    sessions: tuple[SessionSummaryContext, ...] = field(default=())
    progress: ProgressContext | None = None
    conversation: ConversationContext | None = None
    application: ApplicationContext | None = None

    def sections(self) -> tuple[str, ...]:
        """Return the names of the populated sections, in a stable order."""
        present = []
        for name in ("user", "exercise", "workout", "progress", "conversation", "application"):
            if getattr(self, name) is not None:
                present.append(name)
        if self.sessions:
            present.append("sessions")
        return tuple(present)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy, omitting empty sections."""
        from dataclasses import asdict

        payload: dict[str, Any] = {"intent": str(self.intent)}
        for name in ("user", "exercise", "workout", "progress", "conversation", "application"):
            value = getattr(self, name)
            if value is not None:
                payload[name] = asdict(value)
        if self.sessions:
            payload["sessions"] = [asdict(item) for item in self.sessions]
        return payload
