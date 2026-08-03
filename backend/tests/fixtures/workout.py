# file_name: workout.py

"""Builders for workout engine tests."""

from typing import Any

from app.engines.exercise.catalog.exercise_definition import ExerciseDefinition
from app.engines.exercise.catalog.exercise_registry import ExerciseRegistry
from app.engines.workout.workout_profile import WorkoutProfile
from app.engines.workout.workout_template import WorkoutTemplate

EXERCISE_DEFAULTS: dict[str, Any] = {
    "id": "EX-0001",
    "version": "1.0.0",
    "slug": "bodyweight_squats",
    "name": "Bodyweight Squats",
    "category": "Lower Body",
    "difficulty": "Beginner",
    "exercise_type": "Repetition",
    "movement_type": "Compound",
    "equipment": ["none"],
    "primary_muscles": ["Quadriceps"],
    "secondary_muscles": [],
    "instructions": ["Lower your hips."],
}

TEMPLATE_DEFAULTS: dict[str, Any] = {
    "id": "WO-0001",
    "version": "1.0.0",
    "goal": "General Fitness",
    "name": "Test Session",
    "seconds_per_repetition": 3,
    "allow_equipment": False,
    "muscle_emphasis": [],
    "levels": [
        {
            "fitness_level": "Beginner",
            "warm_up_exercises": 1,
            "compound_exercises": 2,
            "isolation_exercises": 1,
            "core_exercises": 1,
            "sets": 2,
            "repetitions": 10,
            "hold_seconds": 20,
            "rest_seconds": 30,
        },
        {
            "fitness_level": "Intermediate",
            "warm_up_exercises": 1,
            "compound_exercises": 3,
            "isolation_exercises": 1,
            "core_exercises": 1,
            "sets": 3,
            "repetitions": 12,
            "hold_seconds": 30,
            "rest_seconds": 40,
        },
        {
            "fitness_level": "Advanced",
            "warm_up_exercises": 1,
            "compound_exercises": 4,
            "isolation_exercises": 2,
            "core_exercises": 2,
            "sets": 3,
            "repetitions": 14,
            "hold_seconds": 40,
            "rest_seconds": 45,
        },
    ],
}

PROFILE_DEFAULTS: dict[str, Any] = {
    "age": 30,
    "gender": "Male",
    "height_cm": 178.0,
    "weight_kg": 78.0,
    "goal": "General Fitness",
    "fitness_level": "Intermediate",
    "available_minutes": 60,
}


def exercise(**overrides: Any) -> ExerciseDefinition:
    """Build one exercise definition."""
    return ExerciseDefinition(**{**EXERCISE_DEFAULTS, **overrides})


def template(**overrides: Any) -> WorkoutTemplate:
    """Build one workout template."""
    return WorkoutTemplate(**{**TEMPLATE_DEFAULTS, **overrides})


def profile(**overrides: Any) -> WorkoutProfile:
    """Build one workout profile."""
    return WorkoutProfile(**{**PROFILE_DEFAULTS, **overrides})


def library() -> ExerciseRegistry:
    """Build a small registry covering every phase and difficulty."""
    return ExerciseRegistry(
        (
            # Warm-up
            exercise(id="EX-0001", slug="jumping_jacks", name="Jumping Jacks",
                     category="Warm-up", movement_type="Compound"),
            exercise(id="EX-0002", slug="high_knees", name="High Knees",
                     category="Warm-up", movement_type="Compound"),
            # Compound
            exercise(id="EX-0003", slug="bodyweight_squats", name="Bodyweight Squats",
                     category="Lower Body", movement_type="Compound",
                     primary_muscles=["Quadriceps", "Glutes"]),
            exercise(id="EX-0004", slug="push_ups", name="Push-ups",
                     category="Upper Body", movement_type="Compound",
                     difficulty="Intermediate", primary_muscles=["Chest"]),
            exercise(id="EX-0005", slug="burpees", name="Burpees",
                     category="Full Body", movement_type="Compound",
                     difficulty="Advanced", primary_muscles=["Quadriceps"]),
            exercise(id="EX-0006", slug="step_ups", name="Step-ups",
                     category="Lower Body", movement_type="Compound",
                     equipment=["step"], primary_muscles=["Glutes"]),
            exercise(id="EX-0013", slug="reverse_lunges", name="Reverse Lunges",
                     category="Lower Body", movement_type="Compound",
                     primary_muscles=["Quadriceps"]),
            # Isolation
            exercise(id="EX-0007", slug="calf_raises", name="Calf Raises",
                     category="Lower Body", movement_type="Isolation",
                     primary_muscles=["Calves"]),
            exercise(id="EX-0008", slug="glute_bridges", name="Glute Bridges",
                     category="Lower Body", movement_type="Isolation",
                     primary_muscles=["Glutes"]),
            exercise(id="EX-0009", slug="wall_sit", name="Wall Sit",
                     category="Lower Body", movement_type="Isolation",
                     exercise_type="Duration", equipment=["wall"],
                     primary_muscles=["Quadriceps"]),
            # Core
            exercise(id="EX-0010", slug="plank", name="Plank", category="Core",
                     movement_type="Isolation", exercise_type="Duration",
                     equipment=["mat_optional"], primary_muscles=["Core"]),
            exercise(id="EX-0011", slug="bicycle_crunches", name="Bicycle Crunches",
                     category="Core", movement_type="Compound",
                     equipment=["mat_optional"], primary_muscles=["Obliques"]),
            exercise(id="EX-0012", slug="leg_raises", name="Leg Raises",
                     category="Core", movement_type="Isolation",
                     difficulty="Intermediate", equipment=["mat_optional"],
                     primary_muscles=["Core"]),
        )
    )
