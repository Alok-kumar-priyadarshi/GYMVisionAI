# file_name: test_food_definition.py

"""Unit tests for the food and meal template schemas."""

import pytest
from pydantic import ValidationError

from app.engines.nutrition.food_definition import (
    DietPreference,
    FoodCategory,
    FoodDefinition,
    MealType,
)
from app.engines.nutrition.meal_template import MealTemplate
from app.engines.workout.workout_profile import FitnessGoal

FOOD_PAYLOAD = {
    "id": "FD-0001",
    "version": "1.0.0",
    "slug": "rolled_oats",
    "name": "Rolled Oats",
    "category": "Grain",
    "calories": 389,
    "protein_g": 16.9,
    "carbohydrates_g": 66.3,
    "fat_g": 6.9,
    "serving_size": "100 g dry",
    "meal_types": ["Breakfast"],
    "diet_tags": ["Vegan", "Vegetarian", "Non Vegetarian"],
}

TEMPLATE_PAYLOAD = {
    "id": "MT-0001",
    "version": "1.0.0",
    "name": "Vegan Oat Breakfast",
    "meal_type": "Breakfast",
    "diet_preference": "Vegan",
    "goals": ["Weight Loss", "Muscle Gain", "General Fitness"],
    "food_ids": ["FD-0001", "FD-0027"],
}


def food(**overrides) -> FoodDefinition:
    return FoodDefinition(**{**FOOD_PAYLOAD, **overrides})


def template(**overrides) -> MealTemplate:
    return MealTemplate(**{**TEMPLATE_PAYLOAD, **overrides})


# ---------------------------------------------------------------------------
# Food
# ---------------------------------------------------------------------------


def test_a_valid_food_is_accepted():
    item = food()

    assert item.category is FoodCategory.GRAIN
    assert item.meal_types == (MealType.BREAKFAST,)
    assert item.suits(DietPreference.VEGAN) is True


def test_foods_are_immutable():
    with pytest.raises(ValidationError):
        food().name = "Other"


def test_unknown_food_fields_are_rejected():
    with pytest.raises(ValidationError):
        food(fibre_g=10)


@pytest.mark.parametrize("food_id", ["FD-1", "F-0001", "fd-0001", ""])
def test_malformed_food_identifiers_are_rejected(food_id):
    with pytest.raises(ValidationError):
        food(id=food_id)


def test_calories_must_be_positive():
    with pytest.raises(ValidationError):
        food(calories=0)


def test_macronutrients_cannot_be_negative():
    with pytest.raises(ValidationError):
        food(protein_g=-1)


def test_a_food_needs_at_least_one_meal_type():
    with pytest.raises(ValidationError):
        food(meal_types=[])


def test_a_food_needs_at_least_one_diet_tag():
    with pytest.raises(ValidationError):
        food(diet_tags=[])


def test_unknown_meal_type_is_rejected():
    with pytest.raises(ValidationError):
        food(meal_types=["Brunch"])


def test_unknown_diet_preference_is_rejected():
    with pytest.raises(ValidationError):
        food(diet_tags=["Pescatarian"])


def test_macronutrients_that_contradict_the_calories_are_rejected():
    # 17 g protein, 66 g carbs and 7 g fat cannot be 50 kcal.
    with pytest.raises(ValidationError) as error:
        food(calories=50)

    assert "kcal" in str(error.value)


def test_fibre_heavy_low_calorie_foods_still_validate():
    # Total carbohydrate overstates the energy of leafy vegetables.
    item = food(
        slug="spinach",
        name="Spinach",
        category="Vegetable",
        calories=23,
        protein_g=2.9,
        carbohydrates_g=3.6,
        fat_g=0.4,
        meal_types=["Lunch"],
    )

    assert item.calories == 23


def test_derived_calories_use_atwater_factors():
    item = food(calories=100, protein_g=10, carbohydrates_g=10, fat_g=2.0)

    assert item.derived_calories == pytest.approx(98.0)


def test_served_at_reports_the_meal():
    item = food(meal_types=["Breakfast", "Morning Snack"])

    assert item.served_at(MealType.MORNING_SNACK) is True
    assert item.served_at(MealType.DINNER) is False


def test_suits_reports_the_dietary_preference():
    item = food(diet_tags=["Non Vegetarian"])

    assert item.suits(DietPreference.NON_VEGETARIAN) is True
    assert item.suits(DietPreference.VEGAN) is False


# ---------------------------------------------------------------------------
# Meal template
# ---------------------------------------------------------------------------


def test_a_valid_template_is_accepted():
    item = template()

    assert item.meal_type is MealType.BREAKFAST
    assert item.diet_preference is DietPreference.VEGAN


def test_templates_are_immutable():
    with pytest.raises(ValidationError):
        template().name = "Other"


def test_a_template_needs_at_least_one_food():
    with pytest.raises(ValidationError):
        template(food_ids=[])


def test_a_template_needs_at_least_one_goal():
    with pytest.raises(ValidationError):
        template(goals=[])


def test_malformed_food_references_are_rejected():
    with pytest.raises(ValidationError) as error:
        template(food_ids=["oats"])

    assert "not a food identifier" in str(error.value)


def test_a_template_cannot_repeat_a_food():
    with pytest.raises(ValidationError) as error:
        template(food_ids=["FD-0001", "FD-0001"])

    assert "more than once" in str(error.value)


def test_a_template_reports_the_goals_it_suits():
    item = template(goals=["Muscle Gain"])

    assert item.suits(FitnessGoal.MUSCLE_GAIN) is True
    assert item.suits(FitnessGoal.WEIGHT_LOSS) is False
