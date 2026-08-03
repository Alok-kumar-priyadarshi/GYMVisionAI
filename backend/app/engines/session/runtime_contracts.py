# file_name: runtime_contracts.py

"""Runtime contracts exchanged with the Workout Session Engine.

Defined by ``docs/02_runtime/12_RUNTIME_CONTRACTS.md`` sections 5, 7 and 10.

Per section 11 every contract is immutable, serialisable, strongly typed,
versioned and framework independent. Nothing here imports FastAPI, SQLAlchemy,
MediaPipe or an AI SDK.

Some documented fields cannot be computed yet and are always ``None``:

``WorkoutState.calories`` and ``SessionSummary.calories``
    No document defines a calorie formula.

``WorkoutState.current_streak``
    Streaks live on the ``Progress`` entity, which needs persistence.

``SessionSummary.average_form_score``
    Form scoring belongs to the Form Validation Engine, which is not built.

They are declared so the contract shape stays stable once those inputs exist.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

CONTRACT_VERSION = "1.0.0"


class WorkoutStatus(StrEnum):
    """Lifecycle states of a workout session.

    Values follow ``12_RUNTIME_CONTRACTS.md`` section 7. The state diagram in
    ``18_WORKOUT_SESSION_ENGINE.md`` section 6 names the rest state ``REST``;
    the contract name ``RESTING`` wins because contracts are authoritative.
    """

    READY = "READY"
    ACTIVE = "ACTIVE"
    RESTING = "RESTING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"


TERMINAL_STATUSES = frozenset({WorkoutStatus.COMPLETED, WorkoutStatus.STOPPED})
"""Statuses from which a session accepts no further progress."""


@dataclass(frozen=True, slots=True)
class RepUpdate:
    """One repetition observation, produced by the Rep Counter Engine.

    Attributes:
        current_rep: Repetitions completed in the current set.
        previous_rep: Repetition count before this update.
        current_set: 1-based index of the set in progress.
        rep_completed: Whether this update completes a repetition.
        total_reps: Repetitions completed across the whole exercise.
        rep_quality: Quality score of the repetition, when form validation is
            available.
        invalid_reps: Repetitions rejected as invalid.
        skipped_reps: Repetitions rejected as incomplete.
        last_completed_state: Final movement state of the completed cycle.
        completion_timestamp: When the repetition completed, in session seconds.
    """

    current_rep: int
    previous_rep: int
    current_set: int
    rep_completed: bool
    total_reps: int
    rep_quality: float | None = None
    invalid_reps: int = 0
    skipped_reps: int = 0
    last_completed_state: str | None = None
    completion_timestamp: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the contract."""
        return {
            "current_rep": self.current_rep,
            "previous_rep": self.previous_rep,
            "current_set": self.current_set,
            "rep_completed": self.rep_completed,
            "total_reps": self.total_reps,
            "rep_quality": self.rep_quality,
            "invalid_reps": self.invalid_reps,
            "skipped_reps": self.skipped_reps,
            "last_completed_state": self.last_completed_state,
            "completion_timestamp": self.completion_timestamp,
        }


@dataclass(frozen=True, slots=True)
class WorkoutState:
    """A snapshot of a workout session, consumed by the frontend.

    Attributes:
        workout_id: Identifier of the workout being performed.
        status: Current lifecycle status.
        exercise_slug: Exercise in progress, or ``None`` once complete.
        exercise_name: Display name of the exercise in progress.
        current_set: 1-based index of the set in progress.
        total_sets: Sets prescribed for the current exercise.
        remaining_sets: Sets left in the current exercise, including the current.
        current_rep: Repetitions completed in the current set.
        target_reps: Repetitions prescribed per set. Zero for a held exercise.
        hold_seconds: Seconds held in the current set. Zero when counting reps.
        target_hold_seconds: Seconds prescribed per set. Zero when counting reps.
        remaining_exercises: Exercises left, including the one in progress.
        workout_seconds: Elapsed session time, excluding paused time.
        exercise_seconds: Elapsed time on the current exercise.
        rest_seconds_remaining: Rest left before work resumes.
        completion_percentage: Completed sets as a percentage of the plan.
        calories: Not computed. See the module docstring.
        current_streak: Not computed. See the module docstring.
    """

    workout_id: str
    status: WorkoutStatus
    exercise_slug: str | None
    exercise_name: str | None
    current_set: int
    total_sets: int
    remaining_sets: int
    current_rep: int
    target_reps: int
    hold_seconds: int
    target_hold_seconds: int
    remaining_exercises: int
    workout_seconds: int
    exercise_seconds: int
    rest_seconds_remaining: int
    completion_percentage: float
    calories: int | None = None
    current_streak: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the contract."""
        return {
            "workout_id": self.workout_id,
            "status": str(self.status),
            "exercise_slug": self.exercise_slug,
            "exercise_name": self.exercise_name,
            "current_set": self.current_set,
            "total_sets": self.total_sets,
            "remaining_sets": self.remaining_sets,
            "current_rep": self.current_rep,
            "target_reps": self.target_reps,
            "hold_seconds": self.hold_seconds,
            "target_hold_seconds": self.target_hold_seconds,
            "remaining_exercises": self.remaining_exercises,
            "workout_seconds": self.workout_seconds,
            "exercise_seconds": self.exercise_seconds,
            "rest_seconds_remaining": self.rest_seconds_remaining,
            "completion_percentage": self.completion_percentage,
            "calories": self.calories,
            "current_streak": self.current_streak,
        }


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """Final statistics of a finished session, forwarded to the Progress Service.

    Attributes:
        workout_id: Identifier of the workout performed.
        status: Terminal status of the session.
        exercises_completed: Exercises finished in full.
        exercises_planned: Exercises the plan contained.
        sets_completed: Sets finished across the session.
        sets_planned: Sets the plan contained.
        reps_completed: Repetitions counted across the session.
        workout_seconds: Total session time, excluding paused time.
        rest_seconds: Total time spent resting.
        completion_percentage: Completed sets as a percentage of the plan.
        calories: Not computed. See the module docstring.
        average_form_score: Not computed. See the module docstring.
        achievements: Not computed. Awarded by the Progress Service.
        personal_records: Not computed. Awarded by the Progress Service.
    """

    workout_id: str
    status: WorkoutStatus
    exercises_completed: int
    exercises_planned: int
    sets_completed: int
    sets_planned: int
    reps_completed: int
    workout_seconds: int
    rest_seconds: int
    completion_percentage: float
    calories: int | None = None
    average_form_score: float | None = None
    achievements: tuple[str, ...] = field(default=())
    personal_records: tuple[str, ...] = field(default=())

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the contract."""
        return {
            "workout_id": self.workout_id,
            "status": str(self.status),
            "exercises_completed": self.exercises_completed,
            "exercises_planned": self.exercises_planned,
            "sets_completed": self.sets_completed,
            "sets_planned": self.sets_planned,
            "reps_completed": self.reps_completed,
            "workout_seconds": self.workout_seconds,
            "rest_seconds": self.rest_seconds,
            "completion_percentage": self.completion_percentage,
            "calories": self.calories,
            "average_form_score": self.average_form_score,
            "achievements": list(self.achievements),
            "personal_records": list(self.personal_records),
        }
