# file_name: __init__.py

"""Nutrition engines.

The Food Catalog Engine is the single source of truth for food data and meal
templates. It never generates diet plans and never calls an LLM.
"""

from app.engines.nutrition.body_profile import BodyProfile
from app.engines.nutrition.diet_plan import DietPlan, MealPortion, PlannedMeal
from app.engines.nutrition.diet_planner import DietPlanner, build_diet_planner
from app.engines.nutrition.diet_rules import (
    DietRules,
    load_cached_diet_rules,
    load_diet_rules,
)
from app.engines.nutrition.food_definition import (
    DietPreference,
    FoodCategory,
    FoodDefinition,
    MealType,
)
from app.engines.nutrition.food_loader import (
    NUTRITION_CONFIGURATION_DIRECTORY,
    FoodLoader,
)
from app.engines.nutrition.food_registry import (
    FoodRegistry,
    build_food_registry,
    load_food_registry,
)
from app.engines.nutrition.meal_template import MealTemplate

__all__ = [
    "BodyProfile",
    "DietPlan",
    "DietPlanner",
    "DietPreference",
    "DietRules",
    "FoodCategory",
    "FoodDefinition",
    "FoodLoader",
    "FoodRegistry",
    "MealPortion",
    "MealTemplate",
    "MealType",
    "NUTRITION_CONFIGURATION_DIRECTORY",
    "PlannedMeal",
    "build_diet_planner",
    "build_food_registry",
    "load_cached_diet_rules",
    "load_diet_rules",
    "load_food_registry",
]
