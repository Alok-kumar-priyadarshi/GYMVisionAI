# file_name: session.py

"""Builders for workout session engine tests."""

from app.engines.exercise.catalog.exercise_definition import Difficulty, ExerciseType
from app.engines.session.runtime_contracts import RepUpdate
from app.engines.workout.workout_plan import (
    WorkoutExercise,
    WorkoutPhase,
    WorkoutPlan,
)
from app.engines.workout.workout_profile import FitnessGoal


class FakeClock:
    """A manually advanced monotonic clock."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward."""
        self.now += seconds


def repetition_exercise(
    display_order: int = 1,
    slug: str = "push_ups",
    sets: int = 2,
    repetitions: int = 3,
    rest_seconds: int = 30,
    phase: WorkoutPhase = WorkoutPhase.COMPOUND,
) -> WorkoutExercise:
    """Build a counted exercise."""
    return WorkoutExercise(
        display_order=display_order,
        phase=phase,
        exercise_id=f"EX-{display_order:04d}",
        slug=slug,
        name=slug.replace("_", " ").title(),
        exercise_type=ExerciseType.REPETITION,
        sets=sets,
        repetitions=repetitions,
        hold_seconds=0,
        rest_seconds=rest_seconds,
    )


def hold_exercise(
    display_order: int = 1,
    slug: str = "plank",
    sets: int = 1,
    hold_seconds: int = 30,
    rest_seconds: int = 20,
) -> WorkoutExercise:
    """Build a held exercise."""
    return WorkoutExercise(
        display_order=display_order,
        phase=WorkoutPhase.CORE,
        exercise_id=f"EX-{display_order:04d}",
        slug=slug,
        name=slug.replace("_", " ").title(),
        exercise_type=ExerciseType.DURATION,
        sets=sets,
        repetitions=0,
        hold_seconds=hold_seconds,
        rest_seconds=rest_seconds,
    )


def plan(*exercises: WorkoutExercise) -> WorkoutPlan:
    """Build a workout plan from the given exercises."""
    chosen = exercises or (repetition_exercise(),)
    return WorkoutPlan(
        template_id="WO-0001",
        name="Test Session",
        goal=FitnessGoal.GENERAL_FITNESS,
        difficulty=Difficulty.BEGINNER,
        estimated_duration_minutes=10,
        exercises=chosen,
    )


def completed_rep(current: int = 1, current_set: int = 1) -> RepUpdate:
    """Build a repetition update that completes a repetition."""
    return RepUpdate(
        current_rep=current,
        previous_rep=current - 1,
        current_set=current_set,
        rep_completed=True,
        total_reps=current,
    )


def partial_rep(current: int = 0, current_set: int = 1) -> RepUpdate:
    """Build a repetition update that completes nothing."""
    return RepUpdate(
        current_rep=current,
        previous_rep=current,
        current_set=current_set,
        rep_completed=False,
        total_reps=current,
    )
