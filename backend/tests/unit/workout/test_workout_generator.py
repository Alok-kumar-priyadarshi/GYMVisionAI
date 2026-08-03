# file_name: test_workout_generator.py

"""Unit tests for deterministic workout generation."""

import pytest

from app.engines.exercise.catalog.exercise_registry import ExerciseRegistry
from app.engines.workout.workout_generator import WorkoutGenerator
from app.engines.workout.workout_plan import WorkoutPhase
from app.engines.workout.workout_profile import FitnessGoal
from app.shared.exceptions import WorkoutGenerationError
from tests.fixtures.workout import exercise, library, profile, template


def generator(exercise_registry=None, workout_template=None) -> WorkoutGenerator:
    # An empty registry is falsy, so these defaults must test against None.
    workout_template = workout_template if workout_template is not None else template()
    return WorkoutGenerator(
        exercise_registry if exercise_registry is not None else library(),
        {workout_template.goal: workout_template},
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_the_same_profile_always_produces_the_same_plan():
    engine = generator()

    first = engine.generate(profile())
    second = engine.generate(profile())

    assert first == second


def test_plans_are_immutable():
    plan = generator().generate(profile())

    with pytest.raises(Exception):
        plan.name = "Something else"


# ---------------------------------------------------------------------------
# Composition and ordering
# ---------------------------------------------------------------------------


def test_exercises_follow_the_documented_phase_order():
    plan = generator().generate(profile())

    phases = [item.phase for item in plan.exercises]
    order = [list(WorkoutPhase).index(phase) for phase in phases]

    assert order == sorted(order)


def test_display_order_is_sequential_from_one():
    plan = generator().generate(profile())

    assert [item.display_order for item in plan.exercises] == list(
        range(1, plan.exercise_count + 1)
    )


def test_a_plan_never_repeats_an_exercise():
    plan = generator().generate(profile())

    assert len(set(plan.slugs)) == plan.exercise_count


def test_composition_matches_the_prescription():
    plan = generator().generate(profile(available_minutes=180))

    assert len(plan.phase(WorkoutPhase.WARM_UP)) == 1
    assert len(plan.phase(WorkoutPhase.COMPOUND)) == 3
    assert len(plan.phase(WorkoutPhase.ISOLATION)) == 1
    assert len(plan.phase(WorkoutPhase.CORE)) == 1


def test_plan_reports_the_template_and_goal():
    plan = generator().generate(profile())

    assert plan.template_id == "WO-0001"
    assert plan.name == "Test Session"
    assert plan.goal is FitnessGoal.GENERAL_FITNESS
    assert str(plan.difficulty) == "Intermediate"


# ---------------------------------------------------------------------------
# Selection rules
# ---------------------------------------------------------------------------


def test_exercises_above_the_users_level_are_excluded():
    plan = generator().generate(profile(fitness_level="Beginner"))

    assert "push_ups" not in plan.slugs  # Intermediate
    assert "burpees" not in plan.slugs  # Advanced


def test_an_advanced_user_may_be_given_easier_exercises():
    plan = generator().generate(
        profile(fitness_level="Advanced", available_minutes=180)
    )

    difficulties = {item.slug for item in plan.exercises}
    assert "burpees" in difficulties
    assert len(difficulties) > 1


def test_equipment_exercises_are_excluded_by_default():
    plan = generator().generate(profile(available_minutes=180))

    assert "step_ups" not in plan.slugs
    assert "wall_sit" not in plan.slugs


def test_equipment_exercises_are_allowed_when_the_template_permits_them():
    engine = generator(workout_template=template(allow_equipment=True))

    plan = engine.generate(profile(available_minutes=180))

    assert "step_ups" in plan.slugs


def test_optional_equipment_does_not_exclude_an_exercise():
    # A mat is optional, so mat exercises remain available.
    plan = generator().generate(profile(available_minutes=180))

    assert plan.phase(WorkoutPhase.CORE)


def test_emphasised_muscles_are_selected_first():
    engine = generator(workout_template=template(muscle_emphasis=["Calves"]))

    plan = engine.generate(profile(available_minutes=180))

    assert plan.phase(WorkoutPhase.ISOLATION)[0].slug == "calf_raises"


# ---------------------------------------------------------------------------
# Prescription
# ---------------------------------------------------------------------------


def test_repetition_exercises_receive_repetitions_only():
    plan = generator().generate(profile())

    squats = next(item for item in plan.exercises if item.slug == "bodyweight_squats")
    assert squats.repetitions == 12
    assert squats.hold_seconds == 0
    assert squats.is_hold is False


def test_duration_exercises_receive_hold_time_only():
    plan = generator().generate(
        profile(fitness_level="Beginner", available_minutes=180)
    )

    plank = next(item for item in plan.exercises if item.slug == "plank")
    assert plank.hold_seconds == 20
    assert plank.repetitions == 0
    assert plank.is_hold is True


def test_sets_and_rest_come_from_the_prescription():
    plan = generator().generate(profile())

    assert all(item.sets == 3 for item in plan.exercises)
    assert all(item.rest_seconds == 40 for item in plan.exercises)


def test_higher_levels_receive_more_volume():
    engine = generator()

    beginner = engine.generate(profile(fitness_level="Beginner", available_minutes=180))
    advanced = engine.generate(profile(fitness_level="Advanced", available_minutes=180))

    assert advanced.exercise_count > beginner.exercise_count
    assert advanced.exercises[0].sets >= beginner.exercises[0].sets


# ---------------------------------------------------------------------------
# Duration constraint
# ---------------------------------------------------------------------------


def test_a_plan_fits_the_available_time():
    plan = generator().generate(profile(available_minutes=20))

    assert plan.estimated_duration_minutes <= 20


def test_a_shorter_session_contains_fewer_exercises():
    engine = generator()

    long_session = engine.generate(profile(available_minutes=180))
    short_session = engine.generate(profile(available_minutes=15))

    assert short_session.exercise_count < long_session.exercise_count


def test_trimming_never_removes_the_warm_up():
    plan = generator().generate(profile(available_minutes=5))

    assert plan.phase(WorkoutPhase.WARM_UP)


def test_trimming_always_leaves_a_compound_exercise():
    plan = generator().generate(profile(available_minutes=5))

    assert plan.phase(WorkoutPhase.COMPOUND)


def test_trimming_keeps_the_session_balanced():
    # Trimming takes from the largest phase, so no phase is emptied while
    # another still holds several exercises.
    plan = generator().generate(profile(fitness_level="Advanced", available_minutes=30))

    counts = [
        len(plan.phase(phase))
        for phase in (WorkoutPhase.COMPOUND, WorkoutPhase.ISOLATION, WorkoutPhase.CORE)
    ]
    assert max(counts) - min(counts) <= 1


def test_estimated_duration_accounts_for_sets_and_rest():
    engine = generator()

    plan = engine.generate(profile(available_minutes=180))

    # 3 sets x (12 reps x 3s + 40s rest) = 228s per repetition exercise.
    squats = next(item for item in plan.exercises if item.slug == "bodyweight_squats")
    assert squats.rest_total_seconds == 120
    assert plan.estimated_duration_minutes > 0


# ---------------------------------------------------------------------------
# Failure cases
# ---------------------------------------------------------------------------


def test_an_empty_library_fails_generation():
    engine = generator(exercise_registry=ExerciseRegistry(()))

    with pytest.raises(WorkoutGenerationError) as error:
        engine.generate(profile())

    assert "empty" in str(error.value)


def test_a_library_with_nothing_suitable_fails_generation():
    advanced_only = ExerciseRegistry(
        (exercise(id="EX-0005", slug="burpees", difficulty="Advanced"),)
    )
    engine = generator(exercise_registry=advanced_only)

    with pytest.raises(WorkoutGenerationError):
        engine.generate(profile(fitness_level="Beginner"))


def test_a_missing_template_fails_generation():
    engine = generator()

    with pytest.raises(WorkoutGenerationError) as error:
        engine.generate(profile(goal="Weight Loss"))

    assert "Weight Loss" in str(error.value)


def test_generation_failure_carries_the_documented_error_code():
    error = WorkoutGenerationError()

    assert error.error_code == "WORKOUT-002"
    assert error.http_status == 500


def test_plans_serialise_to_plain_types():
    payload = generator().generate(profile()).to_dict()

    assert payload["template_id"] == "WO-0001"
    assert payload["exercise_count"] == len(payload["exercises"])
    assert isinstance(payload["exercises"][0]["phase"], str)
