# file_name: __init__.py

"""Exercise catalogue.

Loads, validates and publishes the exercise library defined by the configuration
files in ``backend/configuration/exercise``.

This package answers "which exercises exist and what are they". Analysing a
performed exercise is the detector engine's responsibility.
"""

from app.engines.exercise.catalog.configuration_loader import (
    EXERCISE_CONFIGURATION_DIRECTORY,
    ConfigurationLoader,
)
from app.engines.exercise.catalog.exercise_definition import (
    Difficulty,
    Equipment,
    ExerciseCategory,
    ExerciseDefinition,
    ExerciseType,
    MovementType,
)
from app.engines.exercise.catalog.exercise_registry import (
    ExerciseRegistry,
    build_exercise_registry,
    load_exercise_registry,
)

__all__ = [
    "ConfigurationLoader",
    "Difficulty",
    "EXERCISE_CONFIGURATION_DIRECTORY",
    "Equipment",
    "ExerciseCategory",
    "ExerciseDefinition",
    "ExerciseRegistry",
    "ExerciseType",
    "MovementType",
    "build_exercise_registry",
    "load_exercise_registry",
]
