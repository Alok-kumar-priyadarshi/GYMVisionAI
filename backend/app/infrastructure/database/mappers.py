# file_name: mappers.py

"""Translation between database models and domain entities.

``docs/04_backend/26_PERSISTENCE_LAYER.md`` section 14 requires repositories to
return domain objects and never leak ORM models. All translation lives here, so
repositories stay about querying and the domain stays about behaviour.
"""

from app.domain.entities.diet import DietPlan, Food, Meal, MealItem
from app.domain.entities.exercise import Exercise, ExerciseResult, ExerciseSession
from app.domain.entities.progress import Progress
from app.domain.entities.user import BodyProfile, User
from app.domain.entities.workout import WorkoutExercise, WorkoutPlan, WorkoutSession
from app.infrastructure.database.models import (
    BodyProfileModel,
    DietPlanModel,
    ExerciseModel,
    ExerciseResultModel,
    ExerciseSessionModel,
    FoodModel,
    MealItemModel,
    MealModel,
    ProgressModel,
    UserModel,
    WorkoutExerciseModel,
    WorkoutPlanModel,
    WorkoutSessionModel,
)

# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


def to_user(model: UserModel) -> User:
    """Build a ``User`` from its stored row."""
    return User(
        id=model.id,
        google_id=model.google_id,
        email=model.email,
        full_name=model.full_name,
        profile_picture=model.profile_picture,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_user_model(entity: User) -> UserModel:
    """Build a row from a ``User``."""
    return UserModel(
        id=entity.id,
        google_id=entity.google_id,
        email=entity.email,
        full_name=entity.full_name,
        profile_picture=entity.profile_picture,
        status=str(entity.status),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def apply_user(model: UserModel, entity: User) -> UserModel:
    """Copy a ``User`` onto an existing row."""
    model.email = entity.email
    model.full_name = entity.full_name
    model.profile_picture = entity.profile_picture
    model.status = str(entity.status)
    model.updated_at = entity.updated_at
    return model


def to_body_profile(model: BodyProfileModel) -> BodyProfile:
    """Build a ``BodyProfile`` from its stored row."""
    return BodyProfile(
        id=model.id,
        user_id=model.user_id,
        age=model.age,
        gender=model.gender,
        height_cm=model.height_cm,
        weight_kg=model.weight_kg,
        fitness_goal=model.fitness_goal,
        fitness_level=model.fitness_level,
        problem_areas=tuple(model.problem_areas or ()),
        workout_duration_minutes=model.workout_duration_minutes,
        body_type=model.body_type,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_body_profile_model(entity: BodyProfile) -> BodyProfileModel:
    """Build a row from a ``BodyProfile``."""
    return BodyProfileModel(
        id=entity.id,
        user_id=entity.user_id,
        age=entity.age,
        gender=str(entity.gender),
        height_cm=entity.height_cm,
        weight_kg=entity.weight_kg,
        fitness_goal=str(entity.fitness_goal),
        fitness_level=str(entity.fitness_level),
        problem_areas=entity.problem_areas,
        workout_duration_minutes=entity.workout_duration_minutes,
        body_type=entity.body_type,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def apply_body_profile(model: BodyProfileModel, entity: BodyProfile) -> BodyProfileModel:
    """Copy a ``BodyProfile`` onto an existing row."""
    model.age = entity.age
    model.gender = str(entity.gender)
    model.height_cm = entity.height_cm
    model.weight_kg = entity.weight_kg
    model.fitness_goal = str(entity.fitness_goal)
    model.fitness_level = str(entity.fitness_level)
    model.problem_areas = entity.problem_areas
    model.workout_duration_minutes = entity.workout_duration_minutes
    model.body_type = entity.body_type
    model.updated_at = entity.updated_at
    return model


# ---------------------------------------------------------------------------
# Exercise
# ---------------------------------------------------------------------------


def to_exercise(model: ExerciseModel) -> Exercise:
    """Build an ``Exercise`` from its stored row."""
    return Exercise(
        id=model.id,
        slug=model.slug,
        name=model.name,
        category=model.category,
        difficulty=model.difficulty,
        exercise_type=model.exercise_type,
        movement_type=model.movement_type,
        equipment=tuple(model.equipment or ()),
        primary_muscles=tuple(model.primary_muscles or ()),
        secondary_muscles=tuple(model.secondary_muscles or ()),
        instructions=tuple(model.instructions or ()),
        is_supported=model.is_supported,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_exercise_model(entity: Exercise) -> ExerciseModel:
    """Build a row from an ``Exercise``."""
    return ExerciseModel(
        id=entity.id,
        slug=entity.slug,
        name=entity.name,
        category=str(entity.category),
        difficulty=str(entity.difficulty),
        exercise_type=str(entity.exercise_type),
        movement_type=str(entity.movement_type),
        equipment=[str(item) for item in entity.equipment],
        primary_muscles=list(entity.primary_muscles),
        secondary_muscles=list(entity.secondary_muscles),
        instructions=list(entity.instructions),
        is_supported=entity.is_supported,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def to_exercise_session(model: ExerciseSessionModel) -> ExerciseSession:
    """Build an ``ExerciseSession`` from its stored row."""
    return ExerciseSession(
        id=model.id,
        user_id=model.user_id,
        exercise_id=model.exercise_id,
        status=model.status,
        started_at=model.started_at,
        completed_at=model.completed_at,
        duration_seconds=model.duration_seconds,
        total_reps=model.total_reps,
        average_accuracy=model.average_accuracy,
    )


def to_exercise_session_model(entity: ExerciseSession) -> ExerciseSessionModel:
    """Build a row from an ``ExerciseSession``."""
    return ExerciseSessionModel(
        id=entity.id,
        user_id=entity.user_id,
        exercise_id=entity.exercise_id,
        status=str(entity.status),
        started_at=entity.started_at,
        completed_at=entity.completed_at,
        duration_seconds=entity.duration_seconds,
        total_reps=entity.total_reps,
        average_accuracy=entity.average_accuracy,
    )


def apply_exercise_session(
    model: ExerciseSessionModel, entity: ExerciseSession
) -> ExerciseSessionModel:
    """Copy an ``ExerciseSession`` onto an existing row."""
    model.status = str(entity.status)
    model.completed_at = entity.completed_at
    model.duration_seconds = entity.duration_seconds
    model.total_reps = entity.total_reps
    model.average_accuracy = entity.average_accuracy
    return model


def to_exercise_result(model: ExerciseResultModel) -> ExerciseResult:
    """Build an ``ExerciseResult`` from its stored row."""
    return ExerciseResult(
        id=model.id,
        exercise_session_id=model.exercise_session_id,
        frame_timestamp=model.frame_timestamp,
        current_stage=model.current_stage,
        rep_count=model.rep_count,
        feedback=tuple(model.feedback or ()),
        metrics=dict(model.metrics or {}),
        confidence=model.confidence,
        created_at=model.created_at,
    )


def to_exercise_result_model(entity: ExerciseResult) -> ExerciseResultModel:
    """Build a row from an ``ExerciseResult``."""
    return ExerciseResultModel(
        id=entity.id,
        exercise_session_id=entity.exercise_session_id,
        frame_timestamp=entity.frame_timestamp,
        current_stage=entity.current_stage,
        rep_count=entity.rep_count,
        feedback=list(entity.feedback),
        metrics=dict(entity.metrics),
        confidence=entity.confidence,
        created_at=entity.created_at,
    )


# ---------------------------------------------------------------------------
# Workout
# ---------------------------------------------------------------------------


def to_workout_plan(model: WorkoutPlanModel) -> WorkoutPlan:
    """Build a ``WorkoutPlan`` and its exercises from stored rows."""
    return WorkoutPlan(
        id=model.id,
        user_id=model.user_id,
        title=model.title,
        goal=model.goal,
        difficulty=model.difficulty,
        estimated_duration_minutes=model.estimated_duration_minutes,
        status=model.status,
        exercises=tuple(
            WorkoutExercise(
                id=item.id,
                workout_plan_id=item.workout_plan_id,
                exercise_id=item.exercise_id,
                display_order=item.display_order,
                sets=item.sets,
                repetitions=item.repetitions,
                hold_seconds=item.hold_seconds,
                rest_seconds=item.rest_seconds,
                notes=item.notes,
            )
            for item in model.exercises
        ),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_workout_plan_model(entity: WorkoutPlan) -> WorkoutPlanModel:
    """Build a row and its child rows from a ``WorkoutPlan``."""
    return WorkoutPlanModel(
        id=entity.id,
        user_id=entity.user_id,
        title=entity.title,
        goal=str(entity.goal),
        difficulty=str(entity.difficulty),
        estimated_duration_minutes=entity.estimated_duration_minutes,
        status=str(entity.status),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        exercises=[
            WorkoutExerciseModel(
                id=item.id,
                workout_plan_id=entity.id,
                exercise_id=item.exercise_id,
                display_order=item.display_order,
                sets=item.sets,
                repetitions=item.repetitions,
                hold_seconds=item.hold_seconds,
                rest_seconds=item.rest_seconds,
                notes=item.notes,
            )
            for item in entity.in_order()
        ],
    )


def to_workout_session(model: WorkoutSessionModel) -> WorkoutSession:
    """Build a ``WorkoutSession`` from its stored row."""
    return WorkoutSession(
        id=model.id,
        user_id=model.user_id,
        workout_plan_id=model.workout_plan_id,
        status=model.status,
        started_at=model.started_at,
        completed_at=model.completed_at,
        duration_seconds=model.duration_seconds,
        calories_burned=model.calories_burned,
        average_accuracy=model.average_accuracy,
    )


def to_workout_session_model(entity: WorkoutSession) -> WorkoutSessionModel:
    """Build a row from a ``WorkoutSession``."""
    return WorkoutSessionModel(
        id=entity.id,
        user_id=entity.user_id,
        workout_plan_id=entity.workout_plan_id,
        status=str(entity.status),
        started_at=entity.started_at,
        completed_at=entity.completed_at,
        duration_seconds=entity.duration_seconds,
        calories_burned=entity.calories_burned,
        average_accuracy=entity.average_accuracy,
    )


def apply_workout_session(
    model: WorkoutSessionModel, entity: WorkoutSession
) -> WorkoutSessionModel:
    """Copy a ``WorkoutSession`` onto an existing row."""
    model.status = str(entity.status)
    model.completed_at = entity.completed_at
    model.duration_seconds = entity.duration_seconds
    model.calories_burned = entity.calories_burned
    model.average_accuracy = entity.average_accuracy
    return model


# ---------------------------------------------------------------------------
# Diet
# ---------------------------------------------------------------------------


def to_food(model: FoodModel) -> Food:
    """Build a ``Food`` from its stored row."""
    return Food(
        id=model.id,
        slug=model.slug,
        name=model.name,
        category=model.category,
        calories=model.calories,
        protein_g=model.protein_g,
        carbohydrates_g=model.carbohydrates_g,
        fat_g=model.fat_g,
        serving_size=model.serving_size,
        meal_types=tuple(model.meal_types or ()),
        diet_tags=tuple(model.diet_tags or ()),
    )


def to_food_model(entity: Food) -> FoodModel:
    """Build a row from a ``Food``."""
    return FoodModel(
        id=entity.id,
        slug=entity.slug,
        name=entity.name,
        category=str(entity.category),
        calories=entity.calories,
        protein_g=entity.protein_g,
        carbohydrates_g=entity.carbohydrates_g,
        fat_g=entity.fat_g,
        serving_size=entity.serving_size,
        meal_types=[str(item) for item in entity.meal_types],
        diet_tags=[str(item) for item in entity.diet_tags],
    )


def to_diet_plan(model: DietPlanModel) -> DietPlan:
    """Build a ``DietPlan`` with its meals and portions from stored rows."""
    return DietPlan(
        id=model.id,
        user_id=model.user_id,
        goal=model.goal,
        diet_preference=model.diet_preference,
        estimated_calories=model.estimated_calories,
        water_target_ml=model.water_target_ml,
        status=model.status,
        meals=tuple(
            Meal(
                id=meal.id,
                diet_plan_id=meal.diet_plan_id,
                meal_type=meal.meal_type,
                display_order=meal.display_order,
                items=tuple(
                    MealItem(
                        id=item.id,
                        meal_id=item.meal_id,
                        food_id=item.food_id,
                        servings=item.servings,
                    )
                    for item in meal.items
                ),
            )
            for meal in model.meals
        ),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_diet_plan_model(entity: DietPlan) -> DietPlanModel:
    """Build a row and its child rows from a ``DietPlan``."""
    return DietPlanModel(
        id=entity.id,
        user_id=entity.user_id,
        goal=str(entity.goal),
        diet_preference=str(entity.diet_preference),
        estimated_calories=entity.estimated_calories,
        water_target_ml=entity.water_target_ml,
        status=str(entity.status),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        meals=[
            MealModel(
                id=meal.id,
                diet_plan_id=entity.id,
                meal_type=str(meal.meal_type),
                display_order=meal.display_order,
                items=[
                    MealItemModel(
                        id=item.id,
                        meal_id=meal.id,
                        food_id=item.food_id,
                        servings=item.servings,
                    )
                    for item in meal.items
                ],
            )
            for meal in entity.in_order()
        ],
    )


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


def to_progress(model: ProgressModel) -> Progress:
    """Build a ``Progress`` from its stored row."""
    return Progress(
        id=model.id,
        user_id=model.user_id,
        current_streak=model.current_streak,
        longest_streak=model.longest_streak,
        total_workouts=model.total_workouts,
        total_exercises=model.total_exercises,
        total_minutes=model.total_minutes,
        last_workout_date=model.last_workout_date,
    )


def to_progress_model(entity: Progress) -> ProgressModel:
    """Build a row from a ``Progress``."""
    return ProgressModel(
        id=entity.id,
        user_id=entity.user_id,
        current_streak=entity.current_streak,
        longest_streak=entity.longest_streak,
        total_workouts=entity.total_workouts,
        total_exercises=entity.total_exercises,
        total_minutes=entity.total_minutes,
        last_workout_date=entity.last_workout_date,
    )


def apply_progress(model: ProgressModel, entity: Progress) -> ProgressModel:
    """Copy a ``Progress`` onto an existing row."""
    model.current_streak = entity.current_streak
    model.longest_streak = entity.longest_streak
    model.total_workouts = entity.total_workouts
    model.total_exercises = entity.total_exercises
    model.total_minutes = entity.total_minutes
    model.last_workout_date = entity.last_workout_date
    return model
