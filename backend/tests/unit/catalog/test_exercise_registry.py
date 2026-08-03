# file_name: test_exercise_registry.py

"""Unit tests for the exercise registry, search and filtering."""

import pytest

from app.engines.exercise.catalog.exercise_definition import (
    Difficulty,
    ExerciseCategory,
    ExerciseDefinition,
    ExerciseType,
)
from app.engines.exercise.catalog.exercise_registry import (
    ExerciseRegistry,
    build_exercise_registry,
)
from app.shared.exceptions import ExerciseConfigurationError, ExerciseNotFoundError
from tests.unit.catalog.test_configuration_loader import write_configuration


def definition(**overrides) -> ExerciseDefinition:
    payload = {
        "id": "EX-0015",
        "version": "1.0.0",
        "slug": "push_ups",
        "name": "Push-ups",
        "category": "Upper Body",
        "difficulty": "Intermediate",
        "exercise_type": "Repetition",
        "movement_type": "Compound",
        "equipment": ["none"],
        "primary_muscles": ["Chest"],
        "secondary_muscles": ["Core"],
        "instructions": ["Start in a high plank."],
    }
    return ExerciseDefinition(**{**payload, **overrides})


@pytest.fixture
def registry() -> ExerciseRegistry:
    return ExerciseRegistry(
        (
            definition(),
            definition(
                id="EX-0012",
                slug="wall_sit",
                name="Wall Sit",
                category="Lower Body",
                difficulty="Beginner",
                exercise_type="Duration",
                equipment=["wall"],
                primary_muscles=["Quadriceps"],
                secondary_muscles=["Glutes"],
            ),
            definition(
                id="EX-0020",
                slug="plank",
                name="Plank",
                category="Core",
                difficulty="Beginner",
                exercise_type="Duration",
                equipment=["mat_optional"],
                primary_muscles=["Core"],
            ),
        )
    )


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def test_registry_reports_its_size(registry):
    assert len(registry) == 3


def test_get_returns_the_matching_exercise(registry):
    assert registry.get("push_ups").name == "Push-ups"


def test_get_by_id_returns_the_matching_exercise(registry):
    assert registry.get_by_id("EX-0020").slug == "plank"


def test_membership_uses_the_slug(registry):
    assert "plank" in registry
    assert "bench_press" not in registry


def test_slugs_lists_every_exercise(registry):
    assert set(registry.slugs()) == {"push_ups", "wall_sit", "plank"}


def test_all_returns_every_definition(registry):
    assert len(registry.all()) == 3


def test_unknown_slug_raises_the_documented_error(registry):
    with pytest.raises(ExerciseNotFoundError) as error:
        registry.get("bench_press")

    assert error.value.error_code == "EXERCISE-001"
    assert error.value.http_status == 404


def test_unknown_identifier_raises_the_documented_error(registry):
    with pytest.raises(ExerciseNotFoundError):
        registry.get_by_id("EX-9999")


def test_detector_availability_is_read_from_the_detector_registry(registry):
    assert registry.detector_available("push_ups") is True
    assert registry.detector_available("arm_circles") is False


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("push", {"push_ups"}),
        ("Plank", {"plank"}),
        ("core", {"push_ups", "plank"}),
        ("quadriceps", {"wall_sit"}),
        ("Duration", {"wall_sit", "plank"}),
        ("EX-0012", {"wall_sit"}),
        ("wall", {"wall_sit"}),
        ("beginner", {"wall_sit", "plank"}),
    ],
)
def test_search_matches_every_documented_field(registry, query, expected):
    assert {item.slug for item in registry.search(query)} == expected


def test_search_is_case_insensitive(registry):
    assert registry.search("PUSH") == registry.search("push")


def test_search_returns_nothing_for_a_blank_query(registry):
    assert registry.search("   ") == ()


def test_search_returns_nothing_when_there_is_no_match(registry):
    assert registry.search("deadlift") == ()


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def test_filter_without_arguments_returns_everything(registry):
    assert len(registry.filter()) == 3


def test_filter_by_category(registry):
    results = registry.filter(category=ExerciseCategory.CORE)

    assert [item.slug for item in results] == ["plank"]


def test_filter_by_difficulty(registry):
    results = registry.filter(difficulty=Difficulty.BEGINNER)

    assert {item.slug for item in results} == {"wall_sit", "plank"}


def test_filter_by_exercise_type(registry):
    results = registry.filter(exercise_type=ExerciseType.DURATION)

    assert {item.slug for item in results} == {"wall_sit", "plank"}


def test_filter_by_equipment_free(registry):
    assert {item.slug for item in registry.filter(equipment_free=True)} == {
        "push_ups",
        "plank",
    }
    assert {item.slug for item in registry.filter(equipment_free=False)} == {"wall_sit"}


def test_filters_combine_with_and(registry):
    results = registry.filter(
        difficulty=Difficulty.BEGINNER, exercise_type=ExerciseType.DURATION
    )

    assert {item.slug for item in results} == {"wall_sit", "plank"}


def test_combined_filters_can_exclude_everything(registry):
    assert registry.filter(
        category=ExerciseCategory.CORE, difficulty=Difficulty.ADVANCED
    ) == ()


# ---------------------------------------------------------------------------
# Startup consistency
# ---------------------------------------------------------------------------


def test_startup_fails_when_a_configured_exercise_has_no_detector(tmp_path):
    write_configuration(tmp_path, "arm_circles.yaml", id="EX-0099", slug="arm_circles")

    with pytest.raises(ExerciseConfigurationError) as error:
        build_exercise_registry(tmp_path)

    assert "no detector" in str(error.value)


def test_startup_fails_when_a_detector_has_no_configuration(tmp_path):
    write_configuration(tmp_path, "push_ups.yaml")

    with pytest.raises(ExerciseConfigurationError) as error:
        build_exercise_registry(tmp_path)

    assert "no configuration" in str(error.value)
