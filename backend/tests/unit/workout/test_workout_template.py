# file_name: test_workout_template.py

"""Unit tests for the workout template schema and the user profile contract."""

import pytest
from pydantic import ValidationError

from app.engines.workout.workout_profile import (
    FitnessGoal,
    FitnessLevel,
    WorkoutProfile,
)
from tests.fixtures.workout import profile, template


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------


def test_a_valid_template_is_accepted():
    built = template()

    assert built.id == "WO-0001"
    assert built.goal is FitnessGoal.GENERAL_FITNESS
    assert built.allow_equipment is False


def test_templates_are_immutable():
    with pytest.raises(ValidationError):
        template().name = "Other"


def test_unknown_template_fields_are_rejected():
    with pytest.raises(ValidationError):
        template(intensity="high")


@pytest.mark.parametrize("template_id", ["WO-1", "W-0001", "wo-0001", ""])
def test_malformed_template_identifiers_are_rejected(template_id):
    with pytest.raises(ValidationError):
        template(id=template_id)


def test_unknown_goal_is_rejected():
    with pytest.raises(ValidationError):
        template(goal="Endurance")


def test_a_template_needs_at_least_one_level():
    with pytest.raises(ValidationError):
        template(levels=[])


def test_prescription_is_returned_per_level():
    prescription = template().prescription(FitnessLevel.ADVANCED)

    assert prescription.sets == 3
    assert prescription.repetitions == 14


def test_an_undescribed_level_raises():
    single_level = template(levels=[template().levels[0].model_dump()])

    with pytest.raises(KeyError):
        single_level.prescription(FitnessLevel.ADVANCED)


def test_covers_every_level_detects_a_gap():
    assert template().covers_every_level() is True

    partial = template(levels=[template().levels[0].model_dump()])
    assert partial.covers_every_level() is False


def test_target_exercise_count_sums_the_phases():
    prescription = template().prescription(FitnessLevel.BEGINNER)

    assert prescription.target_exercise_count == 5


def test_difficulty_maps_from_the_fitness_level():
    assert str(template().difficulty_for(FitnessLevel.BEGINNER)) == "Beginner"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sets", 0),
        ("repetitions", 0),
        ("hold_seconds", 1),
        ("rest_seconds", -1),
        ("warm_up_exercises", -1),
        ("compound_exercises", 11),
    ],
)
def test_out_of_range_prescription_values_are_rejected(field, value):
    levels = [dict(level.model_dump()) for level in template().levels]
    levels[0][field] = value

    with pytest.raises(ValidationError):
        template(levels=levels)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def test_a_valid_profile_is_accepted():
    built = profile()

    assert built.fitness_level is FitnessLevel.INTERMEDIATE
    assert built.level_rank == 1


def test_profiles_are_immutable():
    with pytest.raises(ValidationError):
        profile().age = 40


def test_unknown_profile_fields_are_rejected():
    with pytest.raises(ValidationError):
        profile(body_fat=18)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("age", 12),
        ("age", 101),
        ("height_cm", 40),
        ("weight_kg", 10),
        ("available_minutes", 4),
        ("available_minutes", 181),
    ],
)
def test_implausible_profiles_are_rejected(field, value):
    with pytest.raises(ValidationError):
        profile(**{field: value})


def test_unknown_goal_on_a_profile_is_rejected():
    with pytest.raises(ValidationError):
        profile(goal="Endurance")


def test_level_rank_orders_the_levels():
    ranks = [
        profile(fitness_level=level).level_rank
        for level in ("Beginner", "Intermediate", "Advanced")
    ]

    assert ranks == [0, 1, 2]


def test_a_profile_requires_every_field():
    with pytest.raises(ValidationError):
        WorkoutProfile(age=30, gender="Male")
