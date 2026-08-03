# file_name: test_exercise_library.py

"""Integration tests for the shipped exercise library.

These tests load the real configuration files and validate the library against
``docs/12_reference/01_SUPPORTED_EXERCISES.md`` and the detector registry, which
is the integration coverage required by ``19_EXERCISE_ENGINE.md`` section 18.
"""

import pytest

from app.engines.exercise.catalog import load_exercise_registry
from app.engines.exercise.catalog.exercise_definition import (
    Difficulty,
    ExerciseCategory,
    ExerciseType,
)
from app.engines.exercise.detector_registry import (
    DETECTORS,
    HOLD_BASED_EXERCISES,
)

SUPPORTED_EXERCISE_COUNT = 29

# Category totals published by 01_SUPPORTED_EXERCISES.md.
CATEGORY_COUNTS = {
    ExerciseCategory.WARM_UP: 4,
    ExerciseCategory.LOWER_BODY: 10,
    ExerciseCategory.UPPER_BODY: 5,
    ExerciseCategory.CORE: 9,
    ExerciseCategory.FULL_BODY: 1,
}


@pytest.fixture(scope="module")
def registry():
    return load_exercise_registry()


def test_the_library_loads(registry):
    assert len(registry) == SUPPORTED_EXERCISE_COUNT


def test_configuration_is_loaded_once():
    # The registry is cached, so no file system access occurs per request.
    assert load_exercise_registry() is load_exercise_registry()


def test_every_configured_exercise_has_a_detector(registry):
    assert set(registry.slugs()) == set(DETECTORS)


def test_identifiers_are_unique_and_contiguous(registry):
    identifiers = [definition.id for definition in registry.all()]

    assert len(set(identifiers)) == len(identifiers)
    assert identifiers == [
        f"EX-{number:04d}" for number in range(1, SUPPORTED_EXERCISE_COUNT + 1)
    ]


def test_slugs_are_unique(registry):
    slugs = [definition.slug for definition in registry.all()]

    assert len(set(slugs)) == len(slugs)


@pytest.mark.parametrize(("category", "expected"), CATEGORY_COUNTS.items())
def test_category_totals_match_the_reference(registry, category, expected):
    assert len(registry.filter(category=category)) == expected


def test_duration_exercises_match_the_hold_based_detectors(registry):
    duration = {
        definition.slug
        for definition in registry.filter(exercise_type=ExerciseType.DURATION)
    }

    assert duration == HOLD_BASED_EXERCISES


def test_arm_circles_is_absent_from_the_library(registry):
    assert "arm_circles" not in registry


def test_every_exercise_is_fully_described(registry):
    for definition in registry.all():
        assert definition.name.strip()
        assert definition.primary_muscles
        assert len(definition.instructions) >= 3, definition.slug
        assert all(text.strip().endswith(".") for text in definition.instructions)


def test_every_exercise_reports_an_available_detector(registry):
    for definition in registry.all():
        assert registry.detector_available(definition.slug) is True


def test_the_library_covers_every_difficulty(registry):
    for difficulty in Difficulty:
        assert registry.filter(difficulty=difficulty), difficulty


def test_most_exercises_need_no_equipment(registry):
    equipment_free = registry.filter(equipment_free=True)

    assert len(equipment_free) > len(registry) / 2


def test_search_finds_a_known_exercise(registry):
    results = registry.search("push-ups")

    assert any(definition.slug == "push_ups" for definition in results)


def test_search_by_muscle_returns_relevant_exercises(registry):
    results = registry.search("glutes")

    assert {"glute_bridges", "single_leg_glute_bridges"} <= {
        definition.slug for definition in results
    }
