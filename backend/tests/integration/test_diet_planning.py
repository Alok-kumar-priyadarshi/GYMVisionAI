# file_name: test_diet_planning.py

"""Integration tests for diet planning against the shipped configuration.

Covers the weight loss, muscle gain and general fitness scenarios required by
``docs/03_business/23_DIET_PLANNING_ENGINE.md`` section 16, using the real food
catalogue and the real diet rules.
"""

import pytest

from app.engines.nutrition import build_diet_planner, load_food_registry
from app.engines.nutrition.body_profile import BodyProfile
from app.engines.nutrition.food_definition import DietPreference, MealType
from app.engines.workout.workout_profile import FitnessGoal, FitnessLevel

GOALS = list(FitnessGoal)
PREFERENCES = list(DietPreference)
LEVELS = list(FitnessLevel)

PROFILE_DEFAULTS = {
    "age": 28,
    "gender": "Male",
    "height_cm": 178.0,
    "weight_kg": 82.0,
    "goal": "General Fitness",
    "fitness_level": "Intermediate",
    "diet_preference": "Vegetarian",
}


@pytest.fixture(scope="module")
def planner():
    return build_diet_planner()


def profile(**overrides) -> BodyProfile:
    return BodyProfile(**{**PROFILE_DEFAULTS, **overrides})


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("preference", PREFERENCES)
def test_every_goal_and_preference_produces_a_plan(planner, goal, preference):
    plan = planner.generate(profile(goal=goal, diet_preference=preference))

    assert len(plan) == len(MealType)
    assert plan.goal is goal
    assert plan.diet_preference is preference


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("preference", PREFERENCES)
def test_generation_is_reproducible(planner, goal, preference):
    body = profile(goal=goal, diet_preference=preference)

    assert planner.generate(body).to_dict() == planner.generate(body).to_dict()


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("preference", PREFERENCES)
def test_plans_respect_the_dietary_preference(planner, goal, preference):
    plan = planner.generate(profile(goal=goal, diet_preference=preference))

    for meal in plan.meals:
        for portion in meal.portions:
            assert portion.food.suits(preference), portion.food.name


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("preference", PREFERENCES)
def test_every_food_comes_from_the_catalogue(planner, goal, preference):
    # The engine may never invent a food item.
    registry = load_food_registry()
    plan = planner.generate(profile(goal=goal, diet_preference=preference))

    for meal in plan.meals:
        for portion in meal.portions:
            assert portion.food.id in registry


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("preference", PREFERENCES)
def test_foods_are_served_at_the_right_meal(planner, goal, preference):
    plan = planner.generate(profile(goal=goal, diet_preference=preference))

    for meal in plan.meals:
        for portion in meal.portions:
            assert portion.food.served_at(meal.meal_type)


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("preference", PREFERENCES)
def test_a_plan_lands_close_to_its_calorie_target(planner, goal, preference):
    plan = planner.generate(profile(goal=goal, diet_preference=preference))

    drift = abs(plan.estimated_calories - plan.target_calories) / plan.target_calories
    assert drift < 0.15, f"{goal} {preference} drifted {drift:.0%}"


@pytest.mark.parametrize("goal", GOALS)
@pytest.mark.parametrize("preference", PREFERENCES)
def test_no_meal_is_dominated_by_a_single_food(planner, goal, preference):
    # The category caps exist so a meal is not mostly oil or nuts.
    plan = planner.generate(profile(goal=goal, diet_preference=preference))

    for meal in plan.meals:
        if len(meal.portions) < 3 or meal.calories <= 0:
            continue
        largest = max(portion.calories for portion in meal.portions)
        assert largest / meal.calories < 0.7, meal.name


@pytest.mark.parametrize("level", LEVELS)
def test_activity_level_changes_the_target(planner, level):
    plan = planner.generate(profile(fitness_level=level))

    assert 1200 <= plan.target_calories <= 4000


def test_weight_loss_targets_less_than_muscle_gain(planner):
    loss = planner.generate(profile(goal=FitnessGoal.WEIGHT_LOSS))
    gain = planner.generate(profile(goal=FitnessGoal.MUSCLE_GAIN))

    assert loss.target_calories < gain.target_calories


def test_every_plan_recommends_water(planner):
    plan = planner.generate(profile())

    assert plan.water_target_ml >= 2000


def test_a_plan_reports_its_macronutrients(planner):
    plan = planner.generate(profile())

    assert plan.protein_g > 0
    assert plan.carbohydrates_g > 0
    assert plan.fat_g > 0


def test_a_light_profile_still_receives_a_full_plan(planner):
    plan = planner.generate(
        profile(age=65, weight_kg=48, height_cm=152, gender="Female",
                goal=FitnessGoal.WEIGHT_LOSS, fitness_level=FitnessLevel.BEGINNER)
    )

    assert len(plan) == len(MealType)
    assert all(meal.portions for meal in plan.meals)


def test_a_heavy_profile_still_receives_a_full_plan(planner):
    plan = planner.generate(
        profile(age=22, weight_kg=140, height_cm=196,
                goal=FitnessGoal.MUSCLE_GAIN, fitness_level=FitnessLevel.ADVANCED)
    )

    assert len(plan) == len(MealType)
    assert all(meal.portions for meal in plan.meals)


def test_plans_serialise_for_the_api(planner):
    payload = planner.generate(profile()).to_dict()

    assert payload["estimated_calories"] > 0
    assert payload["water_target_ml"] > 0
    assert [meal["meal_type"] for meal in payload["meals"]] == [
        str(meal) for meal in MealType
    ]
