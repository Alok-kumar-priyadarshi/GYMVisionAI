# file_name: __init__.py

"""Workout engine.

Generates deterministic, configuration-driven workout plans from the exercise
library. The engine never calls an AI provider: workout generation is a business
rule, not a language model task.
"""

from app.engines.workout.template_loader import (
    WORKOUT_CONFIGURATION_DIRECTORY,
    TemplateLoader,
    load_workout_templates,
)
from app.engines.workout.workout_generator import (
    WorkoutGenerator,
    build_workout_generator,
)
from app.engines.workout.workout_plan import (
    WorkoutExercise,
    WorkoutPhase,
    WorkoutPlan,
)
from app.engines.workout.workout_profile import (
    FitnessGoal,
    FitnessLevel,
    Gender,
    WorkoutProfile,
)
from app.engines.workout.workout_template import LevelPrescription, WorkoutTemplate

__all__ = [
    "FitnessGoal",
    "FitnessLevel",
    "Gender",
    "LevelPrescription",
    "TemplateLoader",
    "WORKOUT_CONFIGURATION_DIRECTORY",
    "WorkoutExercise",
    "WorkoutGenerator",
    "WorkoutPhase",
    "WorkoutPlan",
    "WorkoutProfile",
    "WorkoutTemplate",
    "build_workout_generator",
    "load_workout_templates",
]
