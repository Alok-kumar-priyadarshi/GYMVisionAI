# file_name: workout_profile.py

"""Input contract for workout generation.

``WorkoutProfile`` carries the user attributes listed in
``docs/03_business/20_WORKOUT_ENGINE.md`` section 6. It is a plain value object:
the Workout Engine never reads the database, so the application layer maps a
stored ``BodyProfile`` onto this contract before calling the engine.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.value_objects.enums import (
    LEVEL_ORDER,
    FitnessGoal,
    FitnessLevel,
    Gender,
)

__all__ = [
    "LEVEL_ORDER",
    "FitnessGoal",
    "FitnessLevel",
    "Gender",
    "WorkoutProfile",
]


class WorkoutProfile(BaseModel):
    """The user attributes a workout is generated from.

    Bounds reject profiles that cannot produce a sensible workout, which
    satisfies the "invalid user profile" error case in section 13.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    age: int = Field(ge=13, le=100)
    gender: Gender
    height_cm: float = Field(gt=50, le=260)
    weight_kg: float = Field(gt=20, le=400)
    goal: FitnessGoal
    fitness_level: FitnessLevel
    available_minutes: int = Field(ge=5, le=180)

    @property
    def level_rank(self) -> int:
        """Return the numeric rank of the user's fitness level."""
        return LEVEL_ORDER[self.fitness_level]
