# file_name: diet_rules.py

"""Configuration governing diet plan generation.

``docs/01_foundation/10_CONFIGURATION_ARCHITECTURE.md`` section 5 assigns
nutrition constants to configuration, and
``docs/03_business/23_DIET_PLANNING_ENGINE.md`` section 18 requires diet plans to
be generated from configuration. Activity factors, goal adjustments, the meal
calorie split and the water rule are therefore data, not code.
"""

import logging
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.engines.nutrition.food_definition import FoodCategory, MealType
from app.engines.workout.workout_profile import FitnessGoal, FitnessLevel
from app.shared.exceptions import NutritionConfigurationError

logger = logging.getLogger(__name__)

RULES_ID_PATTERN = r"^DR-\d{4}$"
VERSION_PATTERN = r"^\d+\.\d+\.\d+$"
CALORIE_SHARE_TOLERANCE = 0.001

DIET_RULES_FILE = (
    Path(__file__).resolve().parents[3]
    / "configuration"
    / "nutrition"
    / "diet_rules.yaml"
)
"""Default location of the diet generation rules."""


class ActivityFactor(BaseModel):
    """Multiplier converting resting energy into daily energy expenditure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fitness_level: FitnessLevel
    factor: float = Field(gt=1.0, le=2.5)


class GoalAdjustment(BaseModel):
    """Multiplier applied to daily energy expenditure for a fitness goal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    goal: FitnessGoal
    calorie_multiplier: float = Field(gt=0.5, le=1.5)


class MealShare(BaseModel):
    """Portion of the daily calorie target allocated to one meal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    meal_type: MealType
    display_order: int = Field(ge=1, le=10)
    calorie_share: float = Field(gt=0.0, le=1.0)


class CategoryServingLimit(BaseModel):
    """Cap on how much of one food category a single meal may contain.

    Calorie-dense categories such as oils would otherwise dominate a meal when
    portions are scaled towards a calorie target. Capping them keeps a plan
    realistic: a lunch should not be mostly olive oil.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: FoodCategory
    maximum_servings: float = Field(gt=0, le=10)


class DietRules(BaseModel):
    """Every value the Diet Planning Engine needs beyond the food catalogue."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=RULES_ID_PATTERN)
    version: str = Field(pattern=VERSION_PATTERN)

    activity_factors: tuple[ActivityFactor, ...] = Field(min_length=1)
    goal_adjustments: tuple[GoalAdjustment, ...] = Field(min_length=1)
    meal_distribution: tuple[MealShare, ...] = Field(min_length=1)
    category_serving_limits: tuple[CategoryServingLimit, ...] = Field(default=())

    water_ml_per_kg: float = Field(gt=0, le=100)
    minimum_water_ml: int = Field(ge=0, le=10000)

    minimum_daily_calories: int = Field(ge=800, le=3000)
    maximum_daily_calories: int = Field(ge=1500, le=6000)

    serving_increment: float = Field(gt=0, le=1)
    minimum_servings: float = Field(gt=0, le=5)
    maximum_servings: float = Field(gt=0, le=10)

    @model_validator(mode="after")
    def _rules_are_complete_and_consistent(self) -> "DietRules":
        """Reject rules that cannot produce a plan for every supported user."""
        levels = {item.fitness_level for item in self.activity_factors}
        if levels != set(FitnessLevel):
            raise ValueError("an activity factor is missing for a fitness level")

        goals = {item.goal for item in self.goal_adjustments}
        if goals != set(FitnessGoal):
            raise ValueError("a calorie adjustment is missing for a goal")

        meals = {item.meal_type for item in self.meal_distribution}
        if meals != set(MealType):
            raise ValueError("a calorie share is missing for a meal")

        total_share = sum(item.calorie_share for item in self.meal_distribution)
        if abs(total_share - 1.0) > CALORIE_SHARE_TOLERANCE:
            raise ValueError(
                f"meal calorie shares total {total_share:.3f} rather than 1.0"
            )

        orders = [item.display_order for item in self.meal_distribution]
        if len(set(orders)) != len(orders):
            raise ValueError("two meals share a display order")

        if self.minimum_daily_calories >= self.maximum_daily_calories:
            raise ValueError("the minimum calorie bound is not below the maximum")

        if self.minimum_servings >= self.maximum_servings:
            raise ValueError("the minimum serving bound is not below the maximum")

        limited = [item.category for item in self.category_serving_limits]
        if len(set(limited)) != len(limited):
            raise ValueError("a food category is capped more than once")

        return self

    def serving_limit(self, category: FoodCategory) -> float | None:
        """Return the serving cap for a food category, if one is configured."""
        for item in self.category_serving_limits:
            if item.category is category:
                return item.maximum_servings
        return None

    def activity_factor(self, fitness_level: FitnessLevel) -> float:
        """Return the activity multiplier for a fitness level."""
        for item in self.activity_factors:
            if item.fitness_level is fitness_level:
                return item.factor
        raise KeyError(fitness_level)

    def goal_multiplier(self, goal: FitnessGoal) -> float:
        """Return the calorie multiplier for a fitness goal."""
        for item in self.goal_adjustments:
            if item.goal is goal:
                return item.calorie_multiplier
        raise KeyError(goal)

    def meals_in_order(self) -> tuple[MealShare, ...]:
        """Return the daily meals sorted by the order they are eaten."""
        return tuple(sorted(self.meal_distribution, key=lambda item: item.display_order))


def load_diet_rules(path: Path | None = None) -> DietRules:
    """Load and validate the diet generation rules.

    Args:
        path: Location of the rules file. Defaults to the project's
            configuration directory.

    Returns:
        The validated rules.

    Raises:
        NutritionConfigurationError: If the file is missing, unparsable or fails
            validation.
    """
    target = path or DIET_RULES_FILE

    if not target.is_file():
        raise NutritionConfigurationError(f"Diet rules file not found: {target}")

    try:
        content = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise NutritionConfigurationError(
            f"{target.name}: file is not valid YAML."
        ) from error
    except OSError as error:
        raise NutritionConfigurationError(
            f"{target.name}: file could not be read."
        ) from error

    if not isinstance(content, dict):
        raise NutritionConfigurationError(
            f"{target.name}: expected a mapping of rule fields, "
            f"received {type(content).__name__}."
        )

    try:
        rules = DietRules(**content)
    except ValidationError as error:
        logger.error("Diet rules validation failed: %s", target.name)
        problems = []
        for issue in error.errors():
            field = ".".join(str(part) for part in issue["loc"]) or "<root>"
            problems.append(
                f"field '{field}': {issue['msg']} (received {issue['input']!r})"
            )
        raise NutritionConfigurationError(
            f"{target.name}: " + "; ".join(problems)
        ) from error

    logger.info("Loaded diet rules %s.", rules.id)
    return rules


@lru_cache(maxsize=1)
def load_cached_diet_rules() -> DietRules:
    """Return the application's diet rules, loading them on first use."""
    return load_diet_rules()
