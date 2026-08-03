# file_name: workout_template.py

"""Schema for workout generation templates.

``docs/01_foundation/10_CONFIGURATION_ARCHITECTURE.md`` section 5 assigns workout
templates to the ``workouts`` configuration category, and
``docs/03_business/20_WORKOUT_ENGINE.md`` section 19 requires generation to be
configuration driven. Sets, repetitions, rest periods and session composition are
therefore data, not code.

One template exists per fitness goal. Each template describes how a session is
composed for every fitness level.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.engines.exercise.catalog.exercise_definition import Difficulty
from app.engines.workout.workout_profile import FitnessGoal, FitnessLevel

TEMPLATE_ID_PATTERN = r"^WO-\d{4}$"
VERSION_PATTERN = r"^\d+\.\d+\.\d+$"


class LevelPrescription(BaseModel):
    """Session parameters for one fitness level.

    The four exercise counts define the session's composition. Their sum is the
    number of exercises the generator aims to select, before any trimming
    required to fit the user's available time.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fitness_level: FitnessLevel
    warm_up_exercises: int = Field(ge=0, le=10)
    compound_exercises: int = Field(ge=0, le=10)
    isolation_exercises: int = Field(ge=0, le=10)
    core_exercises: int = Field(ge=0, le=10)
    sets: int = Field(ge=1, le=10)
    repetitions: int = Field(ge=1, le=100)
    hold_seconds: int = Field(ge=5, le=300)
    rest_seconds: int = Field(ge=0, le=300)

    @property
    def target_exercise_count(self) -> int:
        """Return the number of exercises the session aims to contain."""
        return (
            self.warm_up_exercises
            + self.compound_exercises
            + self.isolation_exercises
            + self.core_exercises
        )


class WorkoutTemplate(BaseModel):
    """Generation rules for one fitness goal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=TEMPLATE_ID_PATTERN)
    version: str = Field(pattern=VERSION_PATTERN)
    goal: FitnessGoal
    name: str = Field(min_length=1)
    seconds_per_repetition: int = Field(ge=1, le=30)
    muscle_emphasis: tuple[str, ...] = Field(default=())
    allow_equipment: bool = False
    levels: tuple[LevelPrescription, ...] = Field(min_length=1)

    def prescription(self, fitness_level: FitnessLevel) -> LevelPrescription:
        """Return the parameters for one fitness level.

        Args:
            fitness_level: The user's experience level.

        Returns:
            The matching prescription.

        Raises:
            KeyError: If the template does not describe that level.
        """
        for level in self.levels:
            if level.fitness_level is fitness_level:
                return level
        raise KeyError(fitness_level)

    def covers_every_level(self) -> bool:
        """Report whether the template describes every fitness level."""
        described = {level.fitness_level for level in self.levels}
        return described == set(FitnessLevel)

    def difficulty_for(self, fitness_level: FitnessLevel) -> Difficulty:
        """Return the plan difficulty corresponding to a fitness level."""
        return Difficulty(str(fitness_level))
