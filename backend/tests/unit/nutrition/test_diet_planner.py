# file_name: test_diet_planner.py

"""Unit tests for deterministic diet plan generation."""

import pytest

from app.engines.nutrition.body_profile import BodyProfile
from app.engines.nutrition.diet_planner import DietPlanner
from app.engines.nutrition.food_definition import FoodCategory, MealType
from app.engines.nutrition.food_registry import FoodRegistry
from app.shared.exceptions import DietGenerationError
from tests.unit.nutrition.test_diet_rules import rules
from tests.unit.nutrition.test_food_definition import food, template

PROFILE_DEFAULTS = {
    "age": 28,
    "gender": "Male",
    "height_cm": 178.0,
    "weight_kg": 82.0,
    "goal": "Weight Loss",
    "fitness_level": "Intermediate",
    "diet_preference": "Vegan",
}


def profile(**overrides) -> BodyProfile:
    return BodyProfile(**{**PROFILE_DEFAULTS, **overrides})


def catalogue() -> FoodRegistry:
    """A catalogue with a vegan template for every meal, plus an oil."""
    foods = (
        food(id="FD-0001", slug="rolled_oats", name="Rolled Oats", category="Grain",
             calories=389, protein_g=16.9, carbohydrates_g=66.3, fat_g=6.9,
             meal_types=["Breakfast", "Morning Snack", "Lunch",
                         "Evening Snack", "Dinner"]),
        food(id="FD-0002", slug="banana", name="Banana", category="Fruit",
             calories=89, protein_g=1.1, carbohydrates_g=22.8, fat_g=0.3,
             meal_types=["Breakfast", "Morning Snack", "Lunch",
                         "Evening Snack", "Dinner"]),
        food(id="FD-0003", slug="olive_oil", name="Olive Oil", category="Fat and Oil",
             calories=884, protein_g=0.0, carbohydrates_g=0.0, fat_g=100.0,
             meal_types=["Breakfast", "Morning Snack", "Lunch",
                         "Evening Snack", "Dinner"]),
    )
    templates = tuple(
        template(
            id=f"MT-{index:04d}",
            name=f"{meal} Plate",
            meal_type=meal,
            food_ids=["FD-0001", "FD-0002", "FD-0003"],
        )
        for index, meal in enumerate(MealType, start=1)
    )
    return FoodRegistry(foods, templates)


def planner(registry: FoodRegistry | None = None, diet_rules=None) -> DietPlanner:
    return DietPlanner(
        registry if registry is not None else catalogue(),
        diet_rules if diet_rules is not None else rules(),
    )


# ---------------------------------------------------------------------------
# Calorie target
# ---------------------------------------------------------------------------


def test_the_calorie_target_uses_mifflin_st_jeor():
    # 10*82 + 6.25*178 - 5*28 + 5 = 1797.5 resting
    # 1797.5 * 1.55 activity * 0.80 weight loss = 2228.9
    assert planner().calorie_target(profile()) == 2229


def test_women_receive_the_female_constant():
    male = planner().calorie_target(profile(gender="Male"))
    female = planner().calorie_target(profile(gender="Female"))

    assert female < male


def test_an_unspecified_gender_falls_between_the_two():
    engine = planner()
    male = engine.calorie_target(profile(gender="Male"))
    female = engine.calorie_target(profile(gender="Female"))
    other = engine.calorie_target(profile(gender="Prefer not to say"))

    assert female < other < male


def test_a_higher_fitness_level_raises_the_target():
    engine = planner()

    beginner = engine.calorie_target(profile(fitness_level="Beginner"))
    advanced = engine.calorie_target(profile(fitness_level="Advanced"))

    assert advanced > beginner


def test_the_goal_adjusts_the_target():
    engine = planner()

    loss = engine.calorie_target(profile(goal="Weight Loss"))
    maintain = engine.calorie_target(profile(goal="General Fitness"))
    gain = engine.calorie_target(profile(goal="Muscle Gain"))

    assert loss < maintain < gain


def test_the_target_is_clamped_to_the_configured_minimum():
    small = profile(age=100, weight_kg=35, height_cm=140, goal="Weight Loss",
                    fitness_level="Beginner")

    assert planner().calorie_target(small) == 1200


def test_the_target_is_clamped_to_the_configured_maximum():
    large = profile(age=18, weight_kg=200, height_cm=210, goal="Muscle Gain",
                    fitness_level="Advanced")

    assert planner().calorie_target(large) == 4000


# ---------------------------------------------------------------------------
# Water
# ---------------------------------------------------------------------------


def test_water_scales_with_body_weight():
    assert planner().water_target(profile(weight_kg=82)) == 2870


def test_water_never_falls_below_the_configured_minimum():
    assert planner().water_target(profile(weight_kg=45)) == 2000


# ---------------------------------------------------------------------------
# Plan structure
# ---------------------------------------------------------------------------


def test_generation_is_deterministic():
    engine = planner()

    assert engine.generate(profile()).to_dict() == engine.generate(profile()).to_dict()


def test_a_plan_contains_every_meal_in_order():
    plan = planner().generate(profile())

    assert [meal.meal_type for meal in plan.meals] == list(MealType)
    assert [meal.display_order for meal in plan.meals] == [1, 2, 3, 4, 5]


def test_meal_targets_follow_the_configured_shares():
    plan = planner().generate(profile())

    lunch = plan.meal(MealType.LUNCH)
    assert lunch.target_calories == round(plan.target_calories * 0.30)


def test_meal_targets_sum_to_the_daily_target():
    plan = planner().generate(profile())

    total = sum(meal.target_calories for meal in plan.meals)
    assert abs(total - plan.target_calories) <= len(plan)


def test_a_plan_reports_its_goal_and_preference():
    plan = planner().generate(profile())

    assert str(plan.goal) == "Weight Loss"
    assert str(plan.diet_preference) == "Vegan"


def test_plans_are_immutable():
    plan = planner().generate(profile())

    with pytest.raises(Exception):
        plan.target_calories = 100


# ---------------------------------------------------------------------------
# Portioning
# ---------------------------------------------------------------------------


def test_calorie_dense_categories_are_capped():
    plan = planner().generate(profile())

    for meal in plan.meals:
        for portion in meal.portions:
            if portion.food.category is FoodCategory.FAT_AND_OIL:
                assert portion.servings <= 0.15


def test_uncapped_foods_absorb_the_remaining_calories():
    plan = planner().generate(profile())
    lunch = plan.meal(MealType.LUNCH)

    oil = next(p for p in lunch.portions if p.food.slug == "olive_oil")
    oats = next(p for p in lunch.portions if p.food.slug == "rolled_oats")

    assert oats.servings > oil.servings


def test_servings_snap_to_the_configured_increment():
    plan = planner().generate(profile())

    for meal in plan.meals:
        for portion in meal.portions:
            if portion.food.category is not FoodCategory.FAT_AND_OIL:
                assert (portion.servings * 4) == pytest.approx(
                    round(portion.servings * 4)
                )


def test_no_portion_is_zero_or_negative():
    plan = planner().generate(profile())

    for meal in plan.meals:
        for portion in meal.portions:
            assert portion.servings > 0


def test_a_meal_lands_near_its_calorie_target():
    plan = planner().generate(profile())

    for meal in plan.meals:
        drift = abs(meal.calories - meal.target_calories) / meal.target_calories
        assert drift < 0.35, meal.meal_type


def test_portion_nutrition_scales_with_servings():
    plan = planner().generate(profile())
    portion = plan.meals[0].portions[0]

    assert portion.calories == pytest.approx(
        portion.food.calories * portion.servings, abs=0.1
    )
    assert portion.protein_g == pytest.approx(
        portion.food.protein_g * portion.servings, abs=0.1
    )


def test_plan_totals_aggregate_the_meals():
    plan = planner().generate(profile())

    assert plan.estimated_calories == pytest.approx(
        sum(meal.calories for meal in plan.meals), abs=0.1
    )


# ---------------------------------------------------------------------------
# Failure cases
# ---------------------------------------------------------------------------


def test_an_empty_catalogue_fails_generation():
    engine = planner(registry=FoodRegistry((), ()))

    with pytest.raises(DietGenerationError) as error:
        engine.generate(profile())

    assert "empty" in str(error.value)


def test_a_missing_template_fails_generation():
    engine = planner()

    with pytest.raises(DietGenerationError) as error:
        engine.generate(profile(diet_preference="Non Vegetarian"))

    assert "Non Vegetarian" in str(error.value)


def test_no_partial_plan_is_returned_on_failure():
    engine = planner(registry=FoodRegistry((), ()))

    with pytest.raises(DietGenerationError):
        engine.generate(profile())


def test_generation_failure_carries_an_error_code():
    error = DietGenerationError()

    assert error.error_code == "SYSTEM-001"
    assert error.http_status == 500


def test_plans_serialise_to_plain_types():
    payload = planner().generate(profile()).to_dict()

    assert isinstance(payload["goal"], str)
    assert len(payload["meals"]) == 5
    assert isinstance(payload["meals"][0]["portions"], list)
