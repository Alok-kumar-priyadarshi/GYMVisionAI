# file_name: test_food_catalog.py

"""Integration tests for the shipped food catalogue.

Covers the integration requirements in
``docs/03_business/24_FOOD_CATALOG_ENGINE.md`` section 18: load every food, load
every meal template and validate their references.
"""

import pytest

from app.engines.nutrition import load_food_registry
from app.engines.nutrition.food_definition import DietPreference, MealType
from app.engines.workout.workout_profile import FitnessGoal

FOOD_COUNT = 36
TEMPLATE_COUNT = 15


@pytest.fixture(scope="module")
def registry():
    return load_food_registry()


def test_the_catalogue_loads(registry):
    assert len(registry) == FOOD_COUNT
    assert len(registry.meal_templates()) == TEMPLATE_COUNT


def test_configuration_is_loaded_once():
    assert load_food_registry() is load_food_registry()


def test_identifiers_are_unique_and_contiguous(registry):
    identifiers = [item.id for item in registry.all()]

    assert identifiers == [f"FD-{number:04d}" for number in range(1, FOOD_COUNT + 1)]


def test_food_names_are_unique(registry):
    names = [item.name for item in registry.all()]

    assert len(set(names)) == len(names)


def test_every_food_declares_usable_nutrition(registry):
    for item in registry.all():
        assert item.calories > 0
        assert item.protein_g >= 0
        assert item.carbohydrates_g >= 0
        assert item.fat_g >= 0
        assert item.serving_size.strip()
        assert item.meal_types
        assert item.diet_tags


def test_every_meal_and_preference_has_at_least_one_template(registry):
    for meal_type in MealType:
        for preference in DietPreference:
            templates = registry.templates_for(
                meal_type=meal_type, diet_preference=preference
            )
            assert templates, f"no {preference} template for {meal_type}"


def test_every_template_resolves_to_real_foods(registry):
    for template in registry.meal_templates():
        foods = registry.foods_in(template)

        assert len(foods) == len(template.food_ids)
        assert all(food.id in registry for food in foods)


def test_every_template_food_fits_its_meal_and_preference(registry):
    for template in registry.meal_templates():
        for food in registry.foods_in(template):
            assert food.served_at(template.meal_type)
            assert food.suits(template.diet_preference)


def test_every_template_supports_every_goal(registry):
    for template in registry.meal_templates():
        for goal in FitnessGoal:
            assert template.suits(goal)


def test_every_meal_and_preference_has_selectable_foods(registry):
    # The Diet Planning Engine must have foods to choose from beyond templates.
    for meal_type in MealType:
        for preference in DietPreference:
            foods = registry.filter(
                meal_type=meal_type, diet_preference=preference
            )
            assert foods, f"no {preference} food for {meal_type}"


def test_the_catalogue_covers_every_category(registry):
    from app.engines.nutrition.food_definition import FoodCategory

    for category in FoodCategory:
        assert registry.filter(category=category), category


def test_vegan_foods_are_available_to_every_preference(registry):
    vegan = registry.filter(diet_preference=DietPreference.VEGAN)

    for food in vegan:
        assert food.suits(DietPreference.VEGETARIAN)
        assert food.suits(DietPreference.NON_VEGETARIAN)


def test_non_vegetarian_foods_are_restricted(registry):
    chicken = registry.get_by_slug("chicken_breast")

    assert chicken.suits(DietPreference.NON_VEGETARIAN) is True
    assert chicken.suits(DietPreference.VEGETARIAN) is False
    assert chicken.suits(DietPreference.VEGAN) is False


def test_search_finds_a_known_food(registry):
    results = registry.search("paneer")

    assert any(item.slug == "paneer" for item in results)
