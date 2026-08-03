# file_name: test_exercise_definition.py

"""Unit tests for the exercise configuration schema."""

import pytest
from pydantic import ValidationError

from app.engines.exercise.catalog.exercise_definition import (
    Difficulty,
    Equipment,
    ExerciseCategory,
    ExerciseDefinition,
    ExerciseType,
)

VALID_PAYLOAD = {
    "id": "EX-0015",
    "version": "1.0.0",
    "slug": "push_ups",
    "name": "Push-ups",
    "category": "Upper Body",
    "difficulty": "Intermediate",
    "exercise_type": "Repetition",
    "movement_type": "Compound",
    "equipment": ["none"],
    "primary_muscles": ["Chest", "Triceps"],
    "secondary_muscles": ["Shoulders", "Core"],
    "instructions": ["Start in a high plank.", "Lower your chest."],
}


def build(**overrides) -> ExerciseDefinition:
    return ExerciseDefinition(**{**VALID_PAYLOAD, **overrides})


def test_a_valid_configuration_is_accepted():
    definition = build()

    assert definition.id == "EX-0015"
    assert definition.category is ExerciseCategory.UPPER_BODY
    assert definition.difficulty is Difficulty.INTERMEDIATE
    assert definition.exercise_type is ExerciseType.REPETITION
    assert definition.equipment == (Equipment.NONE,)


def test_definitions_are_immutable():
    definition = build()

    with pytest.raises(ValidationError):
        definition.name = "Something else"


def test_unknown_fields_are_rejected():
    # A typo in a configuration file must fail rather than be ignored.
    with pytest.raises(ValidationError):
        build(minimum_angle=90)


@pytest.mark.parametrize("exercise_id", ["EX-15", "EX0015", "ex-0015", "EX-00015", ""])
def test_malformed_identifiers_are_rejected(exercise_id):
    with pytest.raises(ValidationError):
        build(id=exercise_id)


@pytest.mark.parametrize("slug", ["Push_Ups", "push-ups", "_push_ups", "push__ups", ""])
def test_malformed_slugs_are_rejected(slug):
    with pytest.raises(ValidationError):
        build(slug=slug)


@pytest.mark.parametrize("version", ["1.0", "v1.0.0", "1", ""])
def test_malformed_versions_are_rejected(version):
    with pytest.raises(ValidationError):
        build(version=version)


def test_unknown_category_is_rejected():
    with pytest.raises(ValidationError):
        build(category="Cardio")


def test_unknown_difficulty_is_rejected():
    with pytest.raises(ValidationError):
        build(difficulty="Expert")


def test_unknown_exercise_type_is_rejected():
    with pytest.raises(ValidationError):
        build(exercise_type="Reps")


def test_unknown_equipment_is_rejected():
    with pytest.raises(ValidationError):
        build(equipment=["barbell"])


@pytest.mark.parametrize(
    "field", ["equipment", "primary_muscles", "instructions"]
)
def test_mandatory_collections_cannot_be_empty(field):
    with pytest.raises(ValidationError):
        build(**{field: []})


def test_secondary_muscles_are_optional():
    payload = dict(VALID_PAYLOAD)
    del payload["secondary_muscles"]

    assert ExerciseDefinition(**payload).secondary_muscles == ()


def test_name_cannot_be_blank():
    with pytest.raises(ValidationError):
        build(name="")


@pytest.mark.parametrize(
    ("equipment", "expected"),
    [
        (["none"], False),
        (["mat_optional"], False),
        (["wall"], True),
        (["chair"], True),
        (["step"], True),
        (["mat_optional", "wall"], True),
    ],
)
def test_requires_equipment_ignores_optional_equipment(equipment, expected):
    assert build(equipment=equipment).requires_equipment is expected


def test_muscles_lists_primary_muscles_first():
    definition = build(
        primary_muscles=["Chest"], secondary_muscles=["Shoulders", "Core"]
    )

    assert definition.muscles == ("Chest", "Shoulders", "Core")
