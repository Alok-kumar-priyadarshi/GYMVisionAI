# file_name: workout.py

"""Workout domain entities.

``docs/04_backend/29_DOMAIN_MODEL.md`` section 8:

``WorkoutPlan``
    Immutable after generation. References supported exercises only.

``WorkoutSession``
    Mutable while active. Locked after completion.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities.user import utc_now
from app.domain.value_objects.enums import (
    Difficulty,
    FitnessGoal,
    SessionStatus,
    WorkoutPlanStatus,
)
from app.domain.value_objects.coercion import as_enum
from app.domain.value_objects.identifier import new_id


@dataclass(frozen=True)
class WorkoutExercise:
    """One exercise prescribed inside a workout plan.

    Frozen because it belongs to a plan that is immutable after generation.
    """

    workout_plan_id: UUID
    exercise_id: UUID
    display_order: int
    sets: int
    repetitions: int = 0
    hold_seconds: int = 0
    rest_seconds: int = 0
    notes: str | None = None
    id: UUID = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.display_order < 1:
            raise ValueError("display order starts at 1")
        if self.sets < 1:
            raise ValueError("an exercise requires at least one set")
        if self.repetitions == 0 and self.hold_seconds == 0:
            raise ValueError(
                "an exercise requires either repetitions or a hold duration"
            )


@dataclass(frozen=True)
class WorkoutPlan:
    """A generated workout plan.

    Frozen because section 8 makes a plan immutable after generation. Changing a
    plan means generating a new one, which keeps completed history truthful.
    """

    user_id: UUID
    title: str
    goal: FitnessGoal
    difficulty: Difficulty
    estimated_duration_minutes: int
    exercises: tuple[WorkoutExercise, ...] = ()
    status: WorkoutPlanStatus = WorkoutPlanStatus.GENERATED
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("a workout plan requires a title")
        if self.estimated_duration_minutes < 1:
            raise ValueError("a workout plan requires an estimated duration")

        orders = [item.display_order for item in self.exercises]
        if len(set(orders)) != len(orders):
            raise ValueError("two exercises share a display order")

        object.__setattr__(self, "goal", as_enum(self.goal, FitnessGoal))
        object.__setattr__(self, "difficulty", as_enum(self.difficulty, Difficulty))
        object.__setattr__(self, "status", as_enum(self.status, WorkoutPlanStatus))
        object.__setattr__(self, "exercises", tuple(self.exercises))

    @property
    def exercise_count(self) -> int:
        """Return the number of exercises in the plan."""
        return len(self.exercises)

    @property
    def total_sets(self) -> int:
        """Return the number of sets the plan prescribes."""
        return sum(item.sets for item in self.exercises)

    def in_order(self) -> tuple[WorkoutExercise, ...]:
        """Return the exercises sorted by the order they are performed."""
        return tuple(sorted(self.exercises, key=lambda item: item.display_order))


@dataclass
class WorkoutSession:
    """One workout performed by a user.

    Mutable while active and locked once completed, per section 8.
    """

    user_id: UUID
    workout_plan_id: UUID
    status: SessionStatus = SessionStatus.CREATED
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
    duration_seconds: int = 0
    calories_burned: int | None = None
    average_accuracy: float | None = None
    id: UUID = field(default_factory=new_id)

    def __post_init__(self) -> None:
        self.status = as_enum(self.status, SessionStatus)

    @property
    def is_active(self) -> bool:
        """Report whether the session still accepts changes."""
        return self.status in (
            SessionStatus.CREATED,
            SessionStatus.RUNNING,
            SessionStatus.PAUSED,
        )

    @property
    def is_completed(self) -> bool:
        """Report whether the session finished successfully."""
        return self.status is SessionStatus.COMPLETED

    def start(self) -> None:
        """Begin the workout."""
        self._require_active()
        self.status = SessionStatus.RUNNING

    def pause(self) -> None:
        """Suspend the workout.

        Raises:
            ValueError: If the workout is not running.
        """
        if self.status is not SessionStatus.RUNNING:
            raise ValueError("only a running workout can be paused")
        self.status = SessionStatus.PAUSED

    def resume(self) -> None:
        """Continue a paused workout.

        Raises:
            ValueError: If the workout is not paused.
        """
        if self.status is not SessionStatus.PAUSED:
            raise ValueError("only a paused workout can be resumed")
        self.status = SessionStatus.RUNNING

    def complete(
        self,
        duration_seconds: int,
        average_accuracy: float | None = None,
        calories_burned: int | None = None,
    ) -> None:
        """Finish the workout and lock it.

        Raises:
            ValueError: If the workout has already finished, or a value is out
                of range.
        """
        self._require_active()
        if duration_seconds < 0:
            raise ValueError("duration cannot be negative")
        if average_accuracy is not None and not 0.0 <= average_accuracy <= 1.0:
            raise ValueError("average accuracy must be between 0.0 and 1.0")

        self.status = SessionStatus.COMPLETED
        self.completed_at = utc_now()
        self.duration_seconds = duration_seconds
        self.average_accuracy = average_accuracy
        self.calories_burned = calories_burned

    def stop(self, duration_seconds: int = 0) -> None:
        """End the workout early, preserving progress."""
        self._require_active()
        self.status = SessionStatus.STOPPED
        self.completed_at = utc_now()
        self.duration_seconds = max(duration_seconds, self.duration_seconds)

    def _require_active(self) -> None:
        if not self.is_active:
            raise ValueError("the workout session has already finished")
