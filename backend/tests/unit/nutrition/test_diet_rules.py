# file_name: test_diet_rules.py

"""Unit tests for the diet rules schema and loader."""

import copy

import pytest
import yaml

from app.engines.nutrition.diet_rules import DietRules, load_diet_rules
from app.engines.nutrition.food_definition import FoodCategory, MealType
from app.engines.workout.workout_profile import FitnessGoal, FitnessLevel
from app.shared.exceptions import NutritionConfigurationError

RULES_PAYLOAD = {
    "id": "DR-0001",
    "version": "1.0.0",
    "activity_factors": [
        {"fitness_level": "Beginner", "factor": 1.375},
        {"fitness_level": "Intermediate", "factor": 1.55},
        {"fitness_level": "Advanced", "factor": 1.725},
    ],
    "goal_adjustments": [
        {"goal": "Weight Loss", "calorie_multiplier": 0.80},
        {"goal": "Muscle Gain", "calorie_multiplier": 1.10},
        {"goal": "General Fitness", "calorie_multiplier": 1.00},
    ],
    "meal_distribution": [
        {"meal_type": "Breakfast", "display_order": 1, "calorie_share": 0.25},
        {"meal_type": "Morning Snack", "display_order": 2, "calorie_share": 0.10},
        {"meal_type": "Lunch", "display_order": 3, "calorie_share": 0.30},
        {"meal_type": "Evening Snack", "display_order": 4, "calorie_share": 0.10},
        {"meal_type": "Dinner", "display_order": 5, "calorie_share": 0.25},
    ],
    "category_serving_limits": [
        {"category": "Fat and Oil", "maximum_servings": 0.15},
        {"category": "Nut and Seed", "maximum_servings": 0.3},
    ],
    "water_ml_per_kg": 35,
    "minimum_water_ml": 2000,
    "minimum_daily_calories": 1200,
    "maximum_daily_calories": 4000,
    "serving_increment": 0.25,
    "minimum_servings": 0.25,
    "maximum_servings": 4.0,
}


def rules(**overrides) -> DietRules:
    return DietRules(**{**copy.deepcopy(RULES_PAYLOAD), **overrides})


def test_valid_rules_are_accepted():
    built = rules()

    assert built.id == "DR-0001"
    assert built.water_ml_per_kg == 35


def test_rules_are_immutable():
    with pytest.raises(Exception):
        rules().water_ml_per_kg = 50


def test_unknown_fields_are_rejected():
    with pytest.raises(Exception):
        rules(protein_target=150)


def test_activity_factors_are_looked_up_by_level():
    assert rules().activity_factor(FitnessLevel.ADVANCED) == 1.725


def test_goal_multipliers_are_looked_up_by_goal():
    assert rules().goal_multiplier(FitnessGoal.WEIGHT_LOSS) == 0.80


def test_meals_are_returned_in_eating_order():
    ordered = [share.meal_type for share in rules().meals_in_order()]

    assert ordered == [
        MealType.BREAKFAST,
        MealType.MORNING_SNACK,
        MealType.LUNCH,
        MealType.EVENING_SNACK,
        MealType.DINNER,
    ]


def test_category_limits_are_looked_up_by_category():
    built = rules()

    assert built.serving_limit(FoodCategory.FAT_AND_OIL) == 0.15
    assert built.serving_limit(FoodCategory.GRAIN) is None


def test_a_missing_activity_factor_is_rejected():
    payload = copy.deepcopy(RULES_PAYLOAD)
    payload["activity_factors"].pop()

    with pytest.raises(Exception) as error:
        DietRules(**payload)

    assert "fitness level" in str(error.value)


def test_a_missing_goal_adjustment_is_rejected():
    payload = copy.deepcopy(RULES_PAYLOAD)
    payload["goal_adjustments"].pop()

    with pytest.raises(Exception) as error:
        DietRules(**payload)

    assert "goal" in str(error.value)


def test_a_missing_meal_share_is_rejected():
    payload = copy.deepcopy(RULES_PAYLOAD)
    payload["meal_distribution"].pop()

    with pytest.raises(Exception) as error:
        DietRules(**payload)

    assert "meal" in str(error.value)


def test_meal_shares_must_total_one():
    payload = copy.deepcopy(RULES_PAYLOAD)
    payload["meal_distribution"][0]["calorie_share"] = 0.50

    with pytest.raises(Exception) as error:
        DietRules(**payload)

    assert "rather than 1.0" in str(error.value)


def test_duplicate_display_orders_are_rejected():
    payload = copy.deepcopy(RULES_PAYLOAD)
    payload["meal_distribution"][1]["display_order"] = 1

    with pytest.raises(Exception) as error:
        DietRules(**payload)

    assert "display order" in str(error.value)


def test_a_category_cannot_be_capped_twice():
    payload = copy.deepcopy(RULES_PAYLOAD)
    payload["category_serving_limits"].append(
        {"category": "Fat and Oil", "maximum_servings": 1.0}
    )

    with pytest.raises(Exception) as error:
        DietRules(**payload)

    assert "capped more than once" in str(error.value)


def test_inverted_calorie_bounds_are_rejected():
    with pytest.raises(Exception) as error:
        rules(minimum_daily_calories=2500, maximum_daily_calories=2000)

    assert "minimum calorie bound" in str(error.value)


def test_inverted_serving_bounds_are_rejected():
    with pytest.raises(Exception) as error:
        rules(minimum_servings=3.0, maximum_servings=1.0)

    assert "minimum serving bound" in str(error.value)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_rules_load_from_a_file(tmp_path):
    path = tmp_path / "diet_rules.yaml"
    path.write_text(yaml.safe_dump(RULES_PAYLOAD), encoding="utf-8")

    assert load_diet_rules(path).id == "DR-0001"


def test_a_missing_rules_file_is_rejected(tmp_path):
    with pytest.raises(NutritionConfigurationError) as error:
        load_diet_rules(tmp_path / "absent.yaml")

    assert "not found" in str(error.value)


def test_malformed_rules_yaml_is_rejected(tmp_path):
    path = tmp_path / "diet_rules.yaml"
    path.write_text("id: [unclosed", encoding="utf-8")

    with pytest.raises(NutritionConfigurationError):
        load_diet_rules(path)


def test_rules_that_are_not_a_mapping_are_rejected(tmp_path):
    path = tmp_path / "diet_rules.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")

    with pytest.raises(NutritionConfigurationError) as error:
        load_diet_rules(path)

    assert "expected a mapping" in str(error.value)


def test_schema_violations_identify_the_field(tmp_path):
    payload = copy.deepcopy(RULES_PAYLOAD)
    payload["water_ml_per_kg"] = 0
    path = tmp_path / "diet_rules.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(NutritionConfigurationError) as error:
        load_diet_rules(path)

    assert "water_ml_per_kg" in str(error.value)
