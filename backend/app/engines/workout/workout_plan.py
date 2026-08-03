# file_name: workout_plan.py

"""Output contract of the Workout Engine.

``WorkoutPlan`` carries the fields listed in
``docs/03_business/20_WORKOUT_ENGINE.md`` section 5. Plans are immutable once
generated, per the engine's implementation rules in section 19.

The plan is a runtime contract, not a database model. Persisting it is the
application layer's responsibility, and the domain entities it maps onto are
``WorkoutPlan`` and ``WorkoutExercise`` in ``docs/04_backend/29_DOMAIN_MODEL.md``.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.engines.exercise.catalog.exercise_definition import (
    Difficulty,
    ExerciseType,
)
from app.engines.workout.workout_profile import FitnessGoal


class WorkoutPhase(StrEnum):
    """Ordered phases of a generated session.

    The order of these members is the order exercises appear in a plan, as
    defined in section 10. That section also lists a cool-down phase, which is
    not produced: the Version 1 exercise library contains no cool-down
    exercises, and the engine may only select supported exercises.
    """

    WARM_UP = "Warm-up"
    COMPOUND = "Compound"
    ISOLATION = "Isolation"
    CORE = "Core"


@dataclass(frozen=True, slots=True)
class WorkoutExercise:
    """One exercise prescribed inside a workout plan.

    Attributes:
        display_order: 1-based position of the exercise in the session.
        phase: Which phase of the session the exercise belongs to.
        exercise_id: Configuration identifier such as ``EX-0015``.
        slug: Stable exercise identifier such as ``push_ups``.
        name: Display name.
        exercise_type: Whether the exercise is counted or held.
        sets: Number of sets to perform.
        repetitions: Repetitions per set. Zero for duration exercises.
        hold_seconds: Seconds to hold per set. Zero for repetition exercises.
        rest_seconds: Rest after each set.
    """

    display_order: int
    phase: WorkoutPhase
    exercise_id: str
    slug: str
    name: str
    exercise_type: ExerciseType
    sets: int
    repetitions: int
    hold_seconds: int
    rest_seconds: int

    @property
    def is_hold(self) -> bool:
        """Report whether the exercise is measured by hold time."""
        return self.exercise_type is ExerciseType.DURATION

    @property
    def rest_total_seconds(self) -> int:
        """Return the total rest seconds prescribed for this exercise."""
        return self.sets * self.rest_seconds

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the prescription."""
        return {
            "display_order": self.display_order,
            "phase": str(self.phase),
            "exercise_id": self.exercise_id,
            "slug": self.slug,
            "name": self.name,
            "exercise_type": str(self.exercise_type),
            "sets": self.sets,
            "repetitions": self.repetitions,
            "hold_seconds": self.hold_seconds,
            "rest_seconds": self.rest_seconds,
        }


@dataclass(frozen=True, slots=True)
class WorkoutPlan:
    """A complete, deterministic workout session.

    Attributes:
        template_id: Identifier of the workout template used, such as ``WO-0001``.
        name: Display name of the session.
        goal: The goal the session was generated for.
        difficulty: Overall difficulty of the session.
        estimated_duration_minutes: Estimated time to complete the session.
        exercises: The prescribed exercises, in performance order.
    """

    template_id: str
    name: str
    goal: FitnessGoal
    difficulty: Difficulty
    estimated_duration_minutes: int
    exercises: tuple[WorkoutExercise, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.exercises, tuple):
            object.__setattr__(self, "exercises", tuple(self.exercises))

    def __len__(self) -> int:
        return len(self.exercises)

    @property
    def exercise_count(self) -> int:
        """Return the number of exercises in the session."""
        return len(self.exercises)

    @property
    def slugs(self) -> tuple[str, ...]:
        """Return the exercise slugs in performance order."""
        return tuple(exercise.slug for exercise in self.exercises)

    def phase(self, phase: WorkoutPhase) -> tuple[WorkoutExercise, ...]:
        """Return the exercises belonging to one phase."""
        return tuple(item for item in self.exercises if item.phase is phase)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the plan."""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "goal": str(self.goal),
            "difficulty": str(self.difficulty),
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "exercise_count": self.exercise_count,
            "exercises": [exercise.to_dict() for exercise in self.exercises],
        }
