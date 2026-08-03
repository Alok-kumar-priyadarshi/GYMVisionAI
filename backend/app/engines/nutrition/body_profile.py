# file_name: body_profile.py

"""Input contract for diet planning.

``BodyProfile`` carries the attributes listed in
``docs/03_business/23_DIET_PLANNING_ENGINE.md`` section 4. It mirrors the
``BodyProfile`` entity in ``docs/04_backend/29_DOMAIN_MODEL.md``, restricted to
the fields the engine actually consumes.

``diet_preference`` is optional on this contract because section 4 marks it
optional. It has no counterpart on the domain entity, which will need one before
a user's preference can be stored.

Goal, level and gender vocabularies are shared with the Workout Engine rather
than redefined, so a user's goal means the same thing in both engines.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.engines.nutrition.food_definition import DietPreference
from app.engines.workout.workout_profile import (
    FitnessGoal,
    FitnessLevel,
    Gender,
)

__all__ = ["BodyProfile", "DietPreference", "FitnessGoal", "FitnessLevel", "Gender"]


class BodyProfile(BaseModel):
    """The user attributes a diet plan is generated from.

    Bounds reject profiles that cannot produce a sensible calorie target, which
    covers the invalid calorie calculation failure in section 12.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    age: int = Field(ge=13, le=100)
    gender: Gender
    height_cm: float = Field(gt=50, le=260)
    weight_kg: float = Field(gt=20, le=400)
    goal: FitnessGoal
    fitness_level: FitnessLevel
    diet_preference: DietPreference = DietPreference.VEGETARIAN
