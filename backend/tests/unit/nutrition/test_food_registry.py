# file_name: test_food_registry.py

"""Unit tests for the food catalogue loader, registry, search and filtering."""

from pathlib import Path

import pytest
import yaml

from app.engines.nutrition.food_definition import (
    DietPreference,
    FoodCategory,
    FoodDefinition,
    MealType,
)
from app.engines.nutrition.food_loader import FoodLoader
from app.engines.nutrition.food_registry import FoodRegistry, build_food_registry
from app.engines.nutrition.meal_template import MealTemplate
from app.engines.workout.workout_profile import FitnessGoal
from app.shared.exceptions import FoodNotFoundError, NutritionConfigurationError
from tests.unit.nutrition.test_food_definition import (
    FOOD_PAYLOAD,
    TEMPLATE_PAYLOAD,
    food,
    template,
)


def write(directory: Path, subdirectory: str, filename: str, payload: dict) -> Path:
    """Write one nutrition configuration file."""
    target = directory / subdirectory
    target.mkdir(parents=True, exist_ok=True)
    path = target / filename
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def write_catalogue(directory: Path, **overrides) -> None:
    """Write a minimal valid catalogue of one food and one template."""
    write(directory, "foods", "oats.yaml", {**FOOD_PAYLOAD, **overrides})
    write(
        directory,
        "meal_templates",
        "breakfast.yaml",
        {**TEMPLATE_PAYLOAD, "food_ids": ["FD-0001"]},
    )


@pytest.fixture
def registry() -> FoodRegistry:
    return FoodRegistry(
        (
            food(),
            food(
                id="FD-0002",
                slug="chicken_breast",
                name="Chicken Breast",
                category="Protein",
                calories=165,
                protein_g=31.0,
                carbohydrates_g=0.0,
                fat_g=3.6,
                meal_types=["Lunch", "Dinner"],
                diet_tags=["Non Vegetarian"],
            ),
            food(
                id="FD-0003",
                slug="apple",
                name="Apple",
                category="Fruit",
                calories=52,
                protein_g=0.3,
                carbohydrates_g=13.8,
                fat_g=0.2,
                meal_types=["Morning Snack", "Evening Snack"],
                diet_tags=["Vegan", "Vegetarian", "Non Vegetarian"],
            ),
        ),
        (template(food_ids=["FD-0001"]),),
    )


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def test_the_catalogue_reports_its_size(registry):
    assert len(registry) == 3


def test_a_food_is_found_by_identifier(registry):
    assert registry.get("FD-0002").name == "Chicken Breast"


def test_a_food_is_found_by_slug(registry):
    assert registry.get_by_slug("apple").id == "FD-0003"


def test_membership_uses_the_identifier(registry):
    assert "FD-0001" in registry
    assert "FD-9999" not in registry


def test_an_unknown_food_raises(registry):
    with pytest.raises(FoodNotFoundError):
        registry.get("FD-9999")


def test_an_unknown_slug_raises(registry):
    with pytest.raises(FoodNotFoundError):
        registry.get_by_slug("pizza")


def test_a_template_is_found_by_identifier(registry):
    assert registry.template("MT-0001").name == "Vegan Oat Breakfast"


def test_an_unknown_template_raises(registry):
    with pytest.raises(FoodNotFoundError):
        registry.template("MT-9999")


def test_template_references_resolve_to_foods(registry):
    resolved = registry.foods_in(registry.template("MT-0001"))

    assert [item.name for item in resolved] == ["Rolled Oats"]


# ---------------------------------------------------------------------------
# Search and filter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("oats", {"FD-0001"}),
        ("Chicken", {"FD-0002"}),
        ("fruit", {"FD-0003"}),
        ("non vegetarian", {"FD-0001", "FD-0002", "FD-0003"}),
        ("dinner", {"FD-0002"}),
        ("FD-0003", {"FD-0003"}),
    ],
)
def test_search_matches_every_documented_field(registry, query, expected):
    assert {item.id for item in registry.search(query)} == expected


def test_search_is_case_insensitive(registry):
    assert registry.search("APPLE") == registry.search("apple")


def test_a_blank_search_matches_nothing(registry):
    assert registry.search("  ") == ()


def test_filter_by_category(registry):
    results = registry.filter(category=FoodCategory.FRUIT)

    assert [item.id for item in results] == ["FD-0003"]


def test_filter_by_meal_type(registry):
    results = registry.filter(meal_type=MealType.DINNER)

    assert [item.id for item in results] == ["FD-0002"]


def test_filter_by_diet_preference(registry):
    results = registry.filter(diet_preference=DietPreference.VEGAN)

    assert {item.id for item in results} == {"FD-0001", "FD-0003"}


def test_filters_combine_with_and(registry):
    results = registry.filter(
        meal_type=MealType.MORNING_SNACK, diet_preference=DietPreference.VEGAN
    )

    assert [item.id for item in results] == ["FD-0003"]


def test_templates_can_be_filtered(registry):
    assert registry.templates_for(meal_type=MealType.BREAKFAST)
    assert registry.templates_for(meal_type=MealType.DINNER) == ()
    assert registry.templates_for(diet_preference=DietPreference.VEGAN)
    assert registry.templates_for(goal=FitnessGoal.MUSCLE_GAIN)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_a_catalogue_loads(tmp_path):
    write_catalogue(tmp_path)

    built = build_food_registry(tmp_path)

    assert len(built) == 1
    assert len(built.meal_templates()) == 1


def test_a_missing_foods_directory_is_rejected(tmp_path):
    with pytest.raises(NutritionConfigurationError) as error:
        FoodLoader(tmp_path).load_foods()

    assert "not found" in str(error.value)


def test_an_empty_foods_directory_is_rejected(tmp_path):
    (tmp_path / "foods").mkdir()

    with pytest.raises(NutritionConfigurationError) as error:
        FoodLoader(tmp_path).load_foods()

    assert "No configuration files" in str(error.value)


def test_malformed_yaml_is_rejected(tmp_path):
    (tmp_path / "foods").mkdir()
    (tmp_path / "foods" / "broken.yaml").write_text("id: [unclosed", encoding="utf-8")

    with pytest.raises(NutritionConfigurationError) as error:
        FoodLoader(tmp_path).load_foods()

    assert "broken.yaml" in str(error.value)


def test_schema_violations_identify_the_file_and_field(tmp_path):
    write(tmp_path, "foods", "bad.yaml", {**FOOD_PAYLOAD, "category": "Snacks"})

    with pytest.raises(NutritionConfigurationError) as error:
        FoodLoader(tmp_path).load_foods()

    message = str(error.value)
    assert "bad.yaml" in message
    assert "category" in message


def test_duplicate_food_identifiers_are_rejected(tmp_path):
    write(tmp_path, "foods", "a.yaml", FOOD_PAYLOAD)
    write(tmp_path, "foods", "b.yaml", {**FOOD_PAYLOAD, "slug": "oats2", "name": "Oats2"})

    with pytest.raises(NutritionConfigurationError) as error:
        FoodLoader(tmp_path).load_foods()

    assert "Duplicate id" in str(error.value)


def test_duplicate_food_names_are_rejected(tmp_path):
    write(tmp_path, "foods", "a.yaml", FOOD_PAYLOAD)
    write(
        tmp_path, "foods", "b.yaml", {**FOOD_PAYLOAD, "id": "FD-0002", "slug": "oats2"}
    )

    with pytest.raises(NutritionConfigurationError) as error:
        FoodLoader(tmp_path).load_foods()

    assert "Duplicate name" in str(error.value)


# ---------------------------------------------------------------------------
# Reference integrity
# ---------------------------------------------------------------------------


def test_a_template_referencing_an_unknown_food_is_rejected(tmp_path):
    write(tmp_path, "foods", "oats.yaml", FOOD_PAYLOAD)
    write(
        tmp_path,
        "meal_templates",
        "breakfast.yaml",
        {**TEMPLATE_PAYLOAD, "food_ids": ["FD-9999"]},
    )

    with pytest.raises(NutritionConfigurationError) as error:
        build_food_registry(tmp_path)

    assert "unknown food" in str(error.value)


def test_a_template_using_a_food_from_another_meal_is_rejected(tmp_path):
    write(tmp_path, "foods", "oats.yaml", FOOD_PAYLOAD)
    write(
        tmp_path,
        "meal_templates",
        "dinner.yaml",
        {**TEMPLATE_PAYLOAD, "meal_type": "Dinner", "food_ids": ["FD-0001"]},
    )

    with pytest.raises(NutritionConfigurationError) as error:
        build_food_registry(tmp_path)

    assert "not served at Dinner" in str(error.value)


def test_a_vegan_template_using_a_non_vegan_food_is_rejected(tmp_path):
    write(
        tmp_path,
        "foods",
        "eggs.yaml",
        {**FOOD_PAYLOAD, "diet_tags": ["Non Vegetarian"]},
    )
    write(
        tmp_path,
        "meal_templates",
        "breakfast.yaml",
        {**TEMPLATE_PAYLOAD, "food_ids": ["FD-0001"]},
    )

    with pytest.raises(NutritionConfigurationError) as error:
        build_food_registry(tmp_path)

    assert "not Vegan" in str(error.value)


def test_configuration_error_carries_the_documented_error_code():
    error = NutritionConfigurationError()

    assert error.error_code == "SYSTEM-001"
    assert error.http_status == 500
