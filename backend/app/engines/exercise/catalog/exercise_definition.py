# file_name: exercise_definition.py

"""Validated definition of one exercise.

``ExerciseDefinition`` is the output contract of the Exercise Engine described in
``docs/03_business/19_EXERCISE_ENGINE.md`` section 5, and the schema every
exercise configuration file is validated against.

Definitions are immutable once loaded, as required by
``docs/01_foundation/10_CONFIGURATION_ARCHITECTURE.md`` principle CFG-001.

Enumeration values match the strings published by
``contracts/exercises/04_GET_EXERCISES.md`` sections 8 and 9, so the API layer
never has to translate them.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.value_objects.enums import (
    Difficulty,
    Equipment,
    ExerciseCategory,
    ExerciseType,
    MovementType,
)

__all__ = [
    "Difficulty",
    "EXERCISE_ID_PATTERN",
    "Equipment",
    "ExerciseCategory",
    "ExerciseDefinition",
    "ExerciseType",
    "MovementType",
    "SLUG_PATTERN",
    "VERSION_PATTERN",
]

EXERCISE_ID_PATTERN = r"^EX-\d{4}$"
SLUG_PATTERN = r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$"
VERSION_PATTERN = r"^\d+\.\d+\.\d+$"


class ExerciseDefinition(BaseModel):
    """One fully validated exercise, loaded from a configuration file.

    Unknown fields are rejected so that a typo in a configuration file fails at
    startup rather than being silently ignored.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=EXERCISE_ID_PATTERN)
    version: str = Field(pattern=VERSION_PATTERN)
    slug: str = Field(pattern=SLUG_PATTERN)
    name: str = Field(min_length=1)
    category: ExerciseCategory
    difficulty: Difficulty
    exercise_type: ExerciseType
    movement_type: MovementType
    equipment: tuple[Equipment, ...] = Field(min_length=1)
    primary_muscles: tuple[str, ...] = Field(min_length=1)
    secondary_muscles: tuple[str, ...] = Field(default=())
    instructions: tuple[str, ...] = Field(min_length=1)

    @property
    def requires_equipment(self) -> bool:
        """Report whether the exercise needs equipment beyond an optional mat."""
        return any(
            item not in (Equipment.NONE, Equipment.MAT_OPTIONAL)
            for item in self.equipment
        )

    @property
    def muscles(self) -> tuple[str, ...]:
        """Return every muscle the exercise targets, primary first."""
        return self.primary_muscles + self.secondary_muscles
