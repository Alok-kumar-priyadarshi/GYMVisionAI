# file_name: diet_planner.py

"""Deterministic daily diet plan generation.

Implements the pipeline in ``docs/03_business/23_DIET_PLANNING_ENGINE.md``
section 6:

    BodyProfile -> Calorie Target -> Meal Selection -> Daily Diet Plan -> DietPlan

The engine never calls an LLM, never recommends supplements or medication and
makes no medical claims. The calorie target is an estimate used only to guide
meal selection, per section 10.

Only foods present in the food catalogue may be used, so the engine cannot
invent a food item.
"""

import logging

from app.engines.nutrition.body_profile import BodyProfile
from app.engines.nutrition.diet_plan import DietPlan, MealPortion, PlannedMeal
from app.engines.nutrition.diet_rules import (
    DietRules,
    MealShare,
    load_cached_diet_rules,
)
from app.engines.nutrition.food_definition import FoodDefinition
from app.engines.nutrition.food_registry import FoodRegistry, load_food_registry
from app.engines.nutrition.meal_template import MealTemplate
from app.engines.workout.workout_profile import Gender
from app.shared.exceptions import DietGenerationError

logger = logging.getLogger(__name__)

# Mifflin-St Jeor resting energy constants.
WEIGHT_COEFFICIENT = 10.0
HEIGHT_COEFFICIENT = 6.25
AGE_COEFFICIENT = 5.0
MALE_CONSTANT = 5.0
FEMALE_CONSTANT = -161.0
UNSPECIFIED_CONSTANT = (MALE_CONSTANT + FEMALE_CONSTANT) / 2


class DietPlanner:
    """Builds daily diet plans from the food catalogue and the diet rules."""

    def __init__(self, registry: FoodRegistry, rules: DietRules) -> None:
        """Create a planner.

        Args:
            registry: The food catalogue, the only source of foods.
            rules: Calorie, water and meal distribution rules.
        """
        self._registry = registry
        self._rules = rules

    def generate(self, profile: BodyProfile) -> DietPlan:
        """Generate a daily diet plan for one body profile.

        Args:
            profile: The user's physical attributes and preferences.

        Returns:
            A complete, immutable diet plan.

        Raises:
            DietGenerationError: If the food catalogue is empty, or no meal
                template exists for the user's goal and dietary preference. No
                partial plan is ever returned.
        """
        logger.info("Diet plan generation started.")

        if not self._registry.all():
            logger.error("Diet generation failed: the food catalogue is empty.")
            raise DietGenerationError("The food catalogue is empty.")

        target_calories = self.calorie_target(profile)
        meals = tuple(
            self._plan_meal(profile, share, target_calories)
            for share in self._rules.meals_in_order()
        )

        plan = DietPlan(
            goal=profile.goal,
            diet_preference=profile.diet_preference,
            target_calories=target_calories,
            water_target_ml=self.water_target(profile),
            meals=meals,
        )

        logger.info(
            "Diet plan generated: %d meals, %d kcal target.",
            len(plan),
            plan.target_calories,
        )
        return plan

    # ------------------------------------------------------------------
    # Calorie target
    # ------------------------------------------------------------------

    def calorie_target(self, profile: BodyProfile) -> int:
        """Estimate the user's daily calorie target.

        Resting energy uses the Mifflin-St Jeor equation, scaled by an activity
        factor and then by the goal's calorie multiplier. The result is clamped
        to the configured bounds so an extreme profile cannot produce an unsafe
        target.

        This is an estimate to guide meal selection, not medical advice.
        """
        resting = (
            WEIGHT_COEFFICIENT * profile.weight_kg
            + HEIGHT_COEFFICIENT * profile.height_cm
            - AGE_COEFFICIENT * profile.age
            + self._gender_constant(profile.gender)
        )

        if resting <= 0:
            logger.error("Diet generation failed: calorie calculation is invalid.")
            raise DietGenerationError("The calorie calculation produced no result.")

        daily = resting * self._rules.activity_factor(profile.fitness_level)
        adjusted = daily * self._rules.goal_multiplier(profile.goal)

        return int(
            round(
                min(
                    max(adjusted, self._rules.minimum_daily_calories),
                    self._rules.maximum_daily_calories,
                )
            )
        )

    @staticmethod
    def _gender_constant(gender: Gender) -> float:
        """Return the Mifflin-St Jeor constant for a gender.

        Users who do not specify a gender receive the midpoint of the two
        published constants, so a plan can still be produced.
        """
        if gender is Gender.MALE:
            return MALE_CONSTANT
        if gender is Gender.FEMALE:
            return FEMALE_CONSTANT
        return UNSPECIFIED_CONSTANT

    def water_target(self, profile: BodyProfile) -> int:
        """Return a suggested daily water intake in millilitres."""
        estimate = profile.weight_kg * self._rules.water_ml_per_kg
        return int(round(max(estimate, self._rules.minimum_water_ml)))

    # ------------------------------------------------------------------
    # Meal selection
    # ------------------------------------------------------------------

    def _plan_meal(
        self, profile: BodyProfile, share: MealShare, target_calories: int
    ) -> PlannedMeal:
        """Build one meal, scaled towards its share of the daily target."""
        template = self._template_for(profile, share)
        foods = self._registry.foods_in(template)
        meal_target = int(round(target_calories * share.calorie_share))

        if sum(food.calories for food in foods) <= 0:
            raise DietGenerationError(
                f"Meal template '{template.id}' contains no usable food energy."
            )

        portions = self._portion(foods, meal_target)

        return PlannedMeal(
            meal_type=share.meal_type,
            display_order=share.display_order,
            name=template.name,
            template_id=template.id,
            portions=portions,
            target_calories=meal_target,
        )

    def _portion(
        self, foods: tuple[FoodDefinition, ...], meal_target: int
    ) -> tuple[MealPortion, ...]:
        """Assign a serving amount to every food in a meal.

        Capped categories are portioned first and never exceed their limit.
        Whatever calories remain are then spread across the uncapped foods, so a
        meal reaches its target using staples rather than oils and nuts.
        """
        capped: dict[str, float] = {}
        capped_calories = 0.0
        free: list[FoodDefinition] = []

        for food in foods:
            limit = self._rules.serving_limit(food.category)
            if limit is None:
                free.append(food)
                continue

            servings = self._round_servings(limit, maximum=limit)
            capped[food.id] = servings
            capped_calories += food.calories * servings

        free_base = sum(food.calories for food in free)
        remaining = max(meal_target - capped_calories, 0.0)
        scale = remaining / free_base if free_base > 0 else self._rules.minimum_servings

        return tuple(
            MealPortion(
                food=food,
                servings=capped.get(food.id) or self._round_servings(scale),
            )
            for food in foods
        )

    def _template_for(self, profile: BodyProfile, share: MealShare) -> MealTemplate:
        """Return the meal template matching the user's goal and preference.

        Raises:
            DietGenerationError: If no template matches.
        """
        candidates = self._registry.templates_for(
            meal_type=share.meal_type,
            diet_preference=profile.diet_preference,
            goal=profile.goal,
        )

        if not candidates:
            logger.error("Diet generation failed: no template for a meal.")
            raise DietGenerationError(
                f"No {profile.diet_preference} meal template is configured for "
                f"{share.meal_type}."
            )

        # Candidates are registry-ordered, so selection stays deterministic.
        return candidates[0]

    def _round_servings(self, scale: float, maximum: float | None = None) -> float:
        """Snap a scaling factor to a practical serving size.

        Portions are rounded to the configured increment and clamped, so a plan
        never asks for an unmeasurable or absurd amount of a single food.

        Args:
            scale: The unrounded serving multiple.
            maximum: An override for the usual upper bound, used by capped
                categories whose limit is smaller than one serving increment.
        """
        increment = self._rules.serving_increment
        upper = self._rules.maximum_servings if maximum is None else maximum

        snapped = round(scale / increment) * increment
        if maximum is not None and snapped > maximum:
            snapped = maximum
        if snapped <= 0:
            snapped = min(self._rules.minimum_servings, upper)

        bounded = min(max(snapped, min(self._rules.minimum_servings, upper)), upper)
        return round(bounded, 4)


def build_diet_planner() -> DietPlanner:
    """Return a planner wired to the application's configuration."""
    return DietPlanner(load_food_registry(), load_cached_diet_rules())
