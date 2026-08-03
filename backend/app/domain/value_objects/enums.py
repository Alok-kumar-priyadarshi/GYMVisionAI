# file_name: enums.py

"""Shared domain vocabulary.

These enumerations are the single definition of the words the product uses:
a goal, a difficulty and a meal mean the same thing in every engine, every
entity and every API response.

They live in the domain layer because dependencies point inward, per
``docs/04_backend/28_BACKEND_ARCHITECTURE.md`` section 12. Engines import from
here; nothing here imports an engine.

Values are the exact strings published by the API contracts, so no layer has to
translate them.
"""

from enum import StrEnum

# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------


class Gender(StrEnum):
    """Gender recorded on a body profile."""

    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    PREFER_NOT_TO_SAY = "Prefer not to say"


class FitnessGoal(StrEnum):
    """Goals a user may train towards."""

    WEIGHT_LOSS = "Weight Loss"
    MUSCLE_GAIN = "Muscle Gain"
    GENERAL_FITNESS = "General Fitness"


class FitnessLevel(StrEnum):
    """A user's training experience."""

    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"


LEVEL_ORDER: dict[FitnessLevel, int] = {
    FitnessLevel.BEGINNER: 0,
    FitnessLevel.INTERMEDIATE: 1,
    FitnessLevel.ADVANCED: 2,
}
"""Ranking used to compare a user's level against an exercise's difficulty."""


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------


class ExerciseCategory(StrEnum):
    """Categories published by ``contracts/exercises/04_GET_EXERCISES.md``."""

    WARM_UP = "Warm-up"
    LOWER_BODY = "Lower Body"
    UPPER_BODY = "Upper Body"
    CORE = "Core"
    FULL_BODY = "Full Body"


class Difficulty(StrEnum):
    """Difficulty of an exercise or a generated plan."""

    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"


class ExerciseType(StrEnum):
    """How an exercise is measured.

    ``REPETITION`` exercises are counted. ``DURATION`` exercises are held, and
    their hold time is accumulated by the workout session engine.
    """

    REPETITION = "Repetition"
    DURATION = "Duration"


class MovementType(StrEnum):
    """Whether an exercise trains several joints or isolates one."""

    COMPOUND = "Compound"
    ISOLATION = "Isolation"


class Equipment(StrEnum):
    """Equipment an exercise may require.

    Every supported exercise is performable at home. ``MAT_OPTIONAL`` marks
    equipment that improves comfort but is not required.
    """

    NONE = "none"
    MAT_OPTIONAL = "mat_optional"
    WALL = "wall"
    CHAIR = "chair"
    STEP = "step"


# ---------------------------------------------------------------------------
# Nutrition
# ---------------------------------------------------------------------------


class MealType(StrEnum):
    """Meals of the day a plan covers."""

    BREAKFAST = "Breakfast"
    MORNING_SNACK = "Morning Snack"
    LUNCH = "Lunch"
    EVENING_SNACK = "Evening Snack"
    DINNER = "Dinner"


class DietPreference(StrEnum):
    """Dietary preferences the catalogue supports."""

    VEGAN = "Vegan"
    VEGETARIAN = "Vegetarian"
    NON_VEGETARIAN = "Non Vegetarian"


class FoodCategory(StrEnum):
    """Food groupings used for search and filtering."""

    GRAIN = "Grain"
    LEGUME = "Legume"
    PROTEIN = "Protein"
    DAIRY = "Dairy"
    VEGETABLE = "Vegetable"
    FRUIT = "Fruit"
    NUT_AND_SEED = "Nut and Seed"
    FAT_AND_OIL = "Fat and Oil"


# ---------------------------------------------------------------------------
# Lifecycles
# ---------------------------------------------------------------------------


class UserStatus(StrEnum):
    """User lifecycle, per ``29_DOMAIN_MODEL.md`` section 7."""

    REGISTERED = "Registered"
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class WorkoutPlanStatus(StrEnum):
    """Workout plan lifecycle, per section 7."""

    GENERATED = "Generated"
    SCHEDULED = "Scheduled"
    COMPLETED = "Completed"
    ARCHIVED = "Archived"


class SessionStatus(StrEnum):
    """Lifecycle shared by workout and exercise sessions, per section 7."""

    CREATED = "Created"
    RUNNING = "Running"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    STOPPED = "Stopped"


class DietPlanStatus(StrEnum):
    """Diet plan lifecycle, per section 7."""

    GENERATED = "Generated"
    ACTIVE = "Active"
    ARCHIVED = "Archived"
