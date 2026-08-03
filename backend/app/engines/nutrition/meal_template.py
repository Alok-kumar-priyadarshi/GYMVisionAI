# file_name: meal_template.py

"""Validated definition of one meal template.

``MealTemplate`` is the second output contract of the Food Catalog Engine,
described in ``docs/03_business/24_FOOD_CATALOG_ENGINE.md`` sections 5 and 11.

A template references food identifiers only. It never duplicates nutritional
data, so changing a food's nutrition changes every template that uses it.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.engines.nutrition.food_definition import (
    FOOD_ID_PATTERN,
    VERSION_PATTERN,
    DietPreference,
    MealType,
)
from app.engines.workout.workout_profile import FitnessGoal

TEMPLATE_ID_PATTERN = r"^MT-\d{4}$"

_FOOD_ID = re.compile(FOOD_ID_PATTERN)


class MealTemplate(BaseModel):
    """A configured meal, expressed as a list of food identifiers.

    Attributes:
        id: Template identifier such as ``MT-0001``.
        version: Configuration version.
        name: Display name of the meal.
        meal_type: Which meal of the day the template covers.
        diet_preference: The dietary preference the template is written for.
        goals: Fitness goals the template may be used for.
        food_ids: Foods that make up the meal.

    Portion sizes are not part of a template. Scaling a meal to a calorie target
    is the Diet Planning Engine's responsibility, per
    ``docs/03_business/23_DIET_PLANNING_ENGINE.md`` sections 9 and 10.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=TEMPLATE_ID_PATTERN)
    version: str = Field(pattern=VERSION_PATTERN)
    name: str = Field(min_length=1)
    meal_type: MealType
    diet_preference: DietPreference
    goals: tuple[FitnessGoal, ...] = Field(min_length=1)
    food_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("food_ids")
    @classmethod
    def _food_ids_are_well_formed(cls, food_ids: tuple[str, ...]) -> tuple[str, ...]:
        """Reject malformed or repeated food references."""
        for food_id in food_ids:
            if not _FOOD_ID.match(food_id):
                raise ValueError(f"'{food_id}' is not a food identifier")

        if len(set(food_ids)) != len(food_ids):
            raise ValueError("the same food is referenced more than once")

        return food_ids

    def suits(self, goal: FitnessGoal) -> bool:
        """Report whether the template may be used for a fitness goal."""
        return goal in self.goals
