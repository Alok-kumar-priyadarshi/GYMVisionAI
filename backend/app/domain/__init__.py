# file_name: __init__.py

"""Domain layer.

The core business model: entities, value objects and repository interfaces.

This layer is the innermost ring of the architecture. It depends on nothing else
in the application and imports no framework, per
``docs/04_backend/28_BACKEND_ARCHITECTURE.md`` section 10. Everything else
depends on it.
"""

from app.domain.entities.diet import DietPlan, Food, Meal, MealItem
from app.domain.entities.exercise import Exercise, ExerciseResult, ExerciseSession
from app.domain.entities.progress import Progress
from app.domain.entities.user import BodyProfile, User, utc_now
from app.domain.entities.workout import WorkoutExercise, WorkoutPlan, WorkoutSession
from app.domain.value_objects.identifier import is_valid_id, new_id, parse_id

__all__ = [
    "BodyProfile",
    "DietPlan",
    "Exercise",
    "ExerciseResult",
    "ExerciseSession",
    "Food",
    "Meal",
    "MealItem",
    "Progress",
    "User",
    "WorkoutExercise",
    "WorkoutPlan",
    "WorkoutSession",
    "is_valid_id",
    "new_id",
    "parse_id",
    "utc_now",
]
