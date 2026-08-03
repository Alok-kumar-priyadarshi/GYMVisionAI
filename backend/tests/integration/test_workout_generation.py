# file_name: test_workout_generation.py

"""Integration tests for workout generation against the shipped configuration.

Covers the beginner, intermediate and advanced scenarios required by
``docs/03_business/20_WORKOUT_ENGINE.md`` section 17, using the real exercise
library and the real workout templates.
"""

import pytest

from app.engines.exercise.catalog import load_exercise_registry
from app.engines.workout import (
    FitnessGoal,
    FitnessLevel,
    WorkoutPhase,
    build_workout_generator,
)
from tests.fixtures.workout import PROFILE_DEFAULTS
from app.engines.workout.workout_profile import WorkoutProfile

LEVELS = list(FitnessLevel)
GOALS = list(FitnessGoal)


@pytest.fixture(scope="module")
def generator():
    return build_workout_generator()


def make_profile(**overrides) -> WorkoutProfile:
    return WorkoutProfile(**{**PROFILE_DEFAULTS, **overrides})


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("level", LEVELS)
def test_every_goal_and_level_produces_a_plan(generator, goal, level):
    plan = generator.generate(make_profile(goal=goal, fitness_level=level))

    assert plan.exercise_count > 0
    assert plan.goal is goal
    assert str(plan.difficulty) == str(level)


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("level", LEVELS)
def test_generation_is_reproducible(generator, goal, level):
    profile = make_profile(goal=goal, fitness_level=level)

    assert generator.generate(profile) == generator.generate(profile)


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("level", LEVELS)
def test_plans_only_contain_supported_exercises(generator, goal, level):
    registry = load_exercise_registry()
    plan = generator.generate(make_profile(goal=goal, fitness_level=level))

    for exercise in plan.exercises:
        assert exercise.slug in registry
        assert registry.detector_available(exercise.slug) is True


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("level", LEVELS)
def test_plans_respect_the_available_time(generator, goal, level):
    profile = make_profile(goal=goal, fitness_level=level, available_minutes=45)

    plan = generator.generate(profile)

    assert plan.estimated_duration_minutes <= 45


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("level", LEVELS)
def test_plans_never_require_equipment(generator, goal, level):
    # Every session must be performable at home with no purchased equipment.
    registry = load_exercise_registry()
    plan = generator.generate(make_profile(goal=goal, fitness_level=level))

    for exercise in plan.exercises:
        assert registry.get(exercise.slug).requires_equipment is False


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("level", LEVELS)
def test_plans_contain_every_phase(generator, goal, level):
    plan = generator.generate(make_profile(goal=goal, fitness_level=level))

    for phase in WorkoutPhase:
        assert plan.phase(phase), f"{goal} {level} has no {phase} exercise"


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("level", LEVELS)
def test_plans_never_repeat_an_exercise(generator, goal, level):
    plan = generator.generate(make_profile(goal=goal, fitness_level=level))

    assert len(set(plan.slugs)) == plan.exercise_count


@pytest.mark.parametrize("goal", GOALS)
def test_beginners_are_never_given_advanced_exercises(generator, goal):
    registry = load_exercise_registry()
    plan = generator.generate(
        make_profile(goal=goal, fitness_level=FitnessLevel.BEGINNER)
    )

    for exercise in plan.exercises:
        assert str(registry.get(exercise.slug).difficulty) == "Beginner"


def test_a_short_session_still_produces_a_usable_workout(generator):
    plan = generator.generate(make_profile(available_minutes=10))

    assert plan.exercise_count >= 2
    assert plan.phase(WorkoutPhase.WARM_UP)
    assert plan.phase(WorkoutPhase.COMPOUND)


def test_a_longer_session_contains_more_work(generator):
    short_session = generator.generate(make_profile(available_minutes=15))
    long_session = generator.generate(make_profile(available_minutes=90))

    assert long_session.exercise_count > short_session.exercise_count


def test_duration_exercises_are_prescribed_as_holds(generator):
    registry = load_exercise_registry()
    plan = generator.generate(
        make_profile(goal=FitnessGoal.GENERAL_FITNESS, available_minutes=90)
    )

    for exercise in plan.exercises:
        if str(registry.get(exercise.slug).exercise_type) == "Duration":
            assert exercise.hold_seconds > 0
            assert exercise.repetitions == 0


def test_templates_are_loaded_once():
    from app.engines.workout import load_workout_templates

    assert load_workout_templates() is load_workout_templates()
