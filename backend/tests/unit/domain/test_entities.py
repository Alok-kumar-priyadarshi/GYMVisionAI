# file_name: test_entities.py

"""Unit tests for the domain entities and their business rules."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from app.domain.entities.diet import DietPlan, Food, Meal, MealItem
from app.domain.entities.exercise import Exercise, ExerciseResult, ExerciseSession
from app.domain.entities.progress import Progress
from app.domain.entities.user import BodyProfile, User
from app.domain.entities.workout import WorkoutExercise, WorkoutPlan, WorkoutSession
from app.domain.value_objects.enums import (
    DietPlanStatus,
    SessionStatus,
    UserStatus,
    WorkoutPlanStatus,
)
from app.domain.value_objects.identifier import new_id


def user(**overrides) -> User:
    payload = {"google_id": "google-1", "email": "user@test.com", "full_name": "Test"}
    return User(**{**payload, **overrides})


def body_profile(**overrides) -> BodyProfile:
    payload = {
        "user_id": new_id(),
        "age": 30,
        "gender": "Male",
        "height_cm": 178.0,
        "weight_kg": 78.0,
        "fitness_goal": "General Fitness",
        "fitness_level": "Intermediate",
    }
    return BodyProfile(**{**payload, **overrides})


def exercise(**overrides) -> Exercise:
    payload = {
        "slug": "push_ups",
        "name": "Push-ups",
        "category": "Upper Body",
        "difficulty": "Intermediate",
        "exercise_type": "Repetition",
        "movement_type": "Compound",
        "equipment": ("none",),
        "primary_muscles": ("Chest",),
    }
    return Exercise(**{**payload, **overrides})


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


def test_a_user_is_created_registered():
    assert user().status is UserStatus.REGISTERED


def test_a_user_receives_a_uuid7_identifier():
    assert user().id.version == 7


def test_a_user_can_be_activated_and_deactivated():
    person = user()
    created_at = person.updated_at

    person.activate()
    assert person.status is UserStatus.ACTIVE
    assert person.updated_at >= created_at

    person.deactivate()
    assert person.status is UserStatus.INACTIVE


def test_a_user_requires_a_google_identity():
    with pytest.raises(ValueError):
        user(google_id="  ")


def test_a_user_requires_a_valid_email():
    with pytest.raises(ValueError):
        user(email="not-an-email")


# ---------------------------------------------------------------------------
# Body profile
# ---------------------------------------------------------------------------


def test_a_body_profile_computes_bmi():
    assert body_profile(height_cm=180, weight_kg=81).bmi == 25.0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("age", 12),
        ("age", 101),
        ("height_cm", 40),
        ("weight_kg", 10),
        ("workout_duration_minutes", 4),
        ("workout_duration_minutes", 200),
    ],
)
def test_implausible_body_profiles_are_rejected(field, value):
    with pytest.raises(ValueError):
        body_profile(**{field: value})


def test_problem_areas_are_stored_immutably():
    profile = body_profile(problem_areas=["belly", "arms"])

    assert profile.problem_areas == ("belly", "arms")


# ---------------------------------------------------------------------------
# Exercise
# ---------------------------------------------------------------------------


def test_exercise_metadata_is_read_only():
    with pytest.raises(FrozenInstanceError):
        exercise().name = "Something else"


def test_an_exercise_requires_a_slug_and_a_muscle():
    with pytest.raises(ValueError):
        exercise(slug=" ")
    with pytest.raises(ValueError):
        exercise(primary_muscles=())


def test_a_duration_exercise_reports_itself_as_a_hold():
    assert exercise(exercise_type="Duration").is_hold is True
    assert exercise().is_hold is False


# ---------------------------------------------------------------------------
# Exercise session
# ---------------------------------------------------------------------------


def test_an_exercise_session_starts_active():
    session = ExerciseSession(user_id=new_id(), exercise_id=new_id())

    assert session.is_active is True
    assert session.status is SessionStatus.CREATED


def test_an_exercise_session_records_progress():
    session = ExerciseSession(user_id=new_id(), exercise_id=new_id())
    session.start()
    session.record(total_reps=5, duration_seconds=30)

    assert session.total_reps == 5
    assert session.duration_seconds == 30


def test_exercise_session_totals_cannot_move_backwards():
    session = ExerciseSession(user_id=new_id(), exercise_id=new_id())
    session.record(total_reps=5, duration_seconds=30)

    with pytest.raises(ValueError):
        session.record(total_reps=4, duration_seconds=30)
    with pytest.raises(ValueError):
        session.record(total_reps=5, duration_seconds=20)


def test_a_completed_exercise_session_is_locked():
    session = ExerciseSession(user_id=new_id(), exercise_id=new_id())
    session.complete(average_accuracy=0.9)

    assert session.is_active is False
    assert session.completed_at is not None

    with pytest.raises(ValueError):
        session.record(total_reps=10, duration_seconds=60)


def test_a_stopped_exercise_session_preserves_progress():
    session = ExerciseSession(user_id=new_id(), exercise_id=new_id())
    session.record(total_reps=3, duration_seconds=20)
    session.stop()

    assert session.status is SessionStatus.STOPPED
    assert session.total_reps == 3


def test_accuracy_is_bounded():
    session = ExerciseSession(user_id=new_id(), exercise_id=new_id())

    with pytest.raises(ValueError):
        session.complete(average_accuracy=1.5)


# ---------------------------------------------------------------------------
# Exercise result
# ---------------------------------------------------------------------------


def test_an_exercise_result_is_immutable():
    result = ExerciseResult(
        exercise_session_id=new_id(), frame_timestamp=1.0, rep_count=3
    )

    with pytest.raises(FrozenInstanceError):
        result.rep_count = 4


def test_exercise_results_validate_their_values():
    with pytest.raises(ValueError):
        ExerciseResult(
            exercise_session_id=new_id(), frame_timestamp=1.0, rep_count=-1
        )
    with pytest.raises(ValueError):
        ExerciseResult(
            exercise_session_id=new_id(),
            frame_timestamp=1.0,
            rep_count=1,
            confidence=2.0,
        )


# ---------------------------------------------------------------------------
# Workout
# ---------------------------------------------------------------------------


def plan(**overrides) -> WorkoutPlan:
    plan_id = new_id()
    payload = {
        "user_id": new_id(),
        "title": "Full Body Balance",
        "goal": "General Fitness",
        "difficulty": "Beginner",
        "estimated_duration_minutes": 30,
        "exercises": (
            WorkoutExercise(
                workout_plan_id=plan_id,
                exercise_id=new_id(),
                display_order=2,
                sets=3,
                repetitions=12,
            ),
            WorkoutExercise(
                workout_plan_id=plan_id,
                exercise_id=new_id(),
                display_order=1,
                sets=2,
                repetitions=10,
            ),
        ),
    }
    return WorkoutPlan(**{**payload, **overrides})


def test_a_workout_plan_is_immutable_after_generation():
    with pytest.raises(FrozenInstanceError):
        plan().title = "Changed"


def test_a_workout_plan_reports_its_totals():
    built = plan()

    assert built.exercise_count == 2
    assert built.total_sets == 5
    assert built.status is WorkoutPlanStatus.GENERATED


def test_a_workout_plan_orders_its_exercises():
    assert [item.display_order for item in plan().in_order()] == [1, 2]


def test_duplicate_display_orders_are_rejected():
    plan_id = new_id()
    duplicated = (
        WorkoutExercise(
            workout_plan_id=plan_id, exercise_id=new_id(), display_order=1,
            sets=1, repetitions=5,
        ),
        WorkoutExercise(
            workout_plan_id=plan_id, exercise_id=new_id(), display_order=1,
            sets=1, repetitions=5,
        ),
    )

    with pytest.raises(ValueError):
        plan(exercises=duplicated)


def test_an_exercise_needs_repetitions_or_a_hold():
    with pytest.raises(ValueError):
        WorkoutExercise(
            workout_plan_id=new_id(), exercise_id=new_id(), display_order=1, sets=3
        )


def test_a_held_exercise_is_accepted():
    held = WorkoutExercise(
        workout_plan_id=new_id(),
        exercise_id=new_id(),
        display_order=1,
        sets=1,
        hold_seconds=30,
    )

    assert held.hold_seconds == 30


# ---------------------------------------------------------------------------
# Workout session
# ---------------------------------------------------------------------------


def session() -> WorkoutSession:
    return WorkoutSession(user_id=new_id(), workout_plan_id=new_id())


def test_a_workout_session_moves_through_its_lifecycle():
    active = session()
    active.start()
    assert active.status is SessionStatus.RUNNING

    active.pause()
    assert active.status is SessionStatus.PAUSED

    active.resume()
    assert active.status is SessionStatus.RUNNING

    active.complete(duration_seconds=1800, average_accuracy=0.88)
    assert active.is_completed is True


def test_a_completed_workout_session_is_locked():
    active = session()
    active.complete(duration_seconds=600)

    with pytest.raises(ValueError):
        active.complete(duration_seconds=700)
    with pytest.raises(ValueError):
        active.start()


def test_only_a_running_session_can_pause():
    with pytest.raises(ValueError):
        session().pause()


def test_only_a_paused_session_can_resume():
    active = session()
    active.start()

    with pytest.raises(ValueError):
        active.resume()


def test_a_stopped_workout_session_keeps_its_duration():
    active = session()
    active.start()
    active.stop(duration_seconds=300)

    assert active.status is SessionStatus.STOPPED
    assert active.duration_seconds == 300


# ---------------------------------------------------------------------------
# Diet
# ---------------------------------------------------------------------------


def food(**overrides) -> Food:
    payload = {
        "slug": "rolled_oats",
        "name": "Rolled Oats",
        "category": "Grain",
        "calories": 389,
        "protein_g": 16.9,
        "carbohydrates_g": 66.3,
        "fat_g": 6.9,
        "serving_size": "100 g dry",
        "meal_types": ("Breakfast",),
        "diet_tags": ("Vegan", "Vegetarian", "Non Vegetarian"),
    }
    return Food(**{**payload, **overrides})


def test_food_is_read_only():
    with pytest.raises(FrozenInstanceError):
        food().calories = 1


def test_food_validates_its_nutrition():
    with pytest.raises(ValueError):
        food(calories=0)
    with pytest.raises(ValueError):
        food(protein_g=-1)


def test_food_reports_its_dietary_suitability():
    assert food().suits("Vegan") is True
    assert food(diet_tags=("Non Vegetarian",)).suits("Vegan") is False


def test_a_meal_item_requires_a_positive_serving():
    with pytest.raises(ValueError):
        MealItem(meal_id=new_id(), food_id=new_id(), servings=0)


def test_a_diet_plan_orders_and_finds_its_meals():
    plan_id = new_id()
    built = DietPlan(
        user_id=new_id(),
        goal="Weight Loss",
        estimated_calories=1800,
        water_target_ml=2500,
        meals=(
            Meal(diet_plan_id=plan_id, meal_type="Dinner", display_order=5),
            Meal(diet_plan_id=plan_id, meal_type="Breakfast", display_order=1),
        ),
    )

    assert [meal.display_order for meal in built.in_order()] == [1, 5]
    assert built.meal("Breakfast") is not None
    assert built.meal("Lunch") is None


def test_a_diet_plan_moves_through_its_lifecycle():
    built = DietPlan(
        user_id=new_id(), goal="Weight Loss", estimated_calories=1800,
        water_target_ml=2500,
    )

    built.activate()
    assert built.status is DietPlanStatus.ACTIVE

    built.archive()
    assert built.status is DietPlanStatus.ARCHIVED


def test_a_diet_plan_validates_its_targets():
    with pytest.raises(ValueError):
        DietPlan(
            user_id=new_id(), goal="Weight Loss", estimated_calories=0,
            water_target_ml=2500,
        )


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


def test_a_first_workout_starts_a_streak():
    progress = Progress(user_id=new_id())
    progress.record_workout(date(2026, 8, 1), exercises_completed=6, duration_minutes=40)

    assert progress.current_streak == 1
    assert progress.longest_streak == 1
    assert progress.total_workouts == 1


def test_consecutive_days_extend_the_streak():
    progress = Progress(user_id=new_id())
    for day in (1, 2, 3):
        progress.record_workout(date(2026, 8, day), 5, 30)

    assert progress.current_streak == 3
    assert progress.longest_streak == 3


def test_a_second_workout_on_the_same_day_does_not_extend_the_streak():
    progress = Progress(user_id=new_id())
    progress.record_workout(date(2026, 8, 1), 5, 30)
    progress.record_workout(date(2026, 8, 1), 4, 25)

    assert progress.current_streak == 1
    assert progress.total_workouts == 2


def test_a_missed_day_resets_the_streak_but_keeps_the_record():
    progress = Progress(user_id=new_id())
    for day in (1, 2, 3):
        progress.record_workout(date(2026, 8, day), 5, 30)
    progress.record_workout(date(2026, 8, 6), 5, 30)

    assert progress.current_streak == 1
    assert progress.longest_streak == 3


def test_a_streak_decays_when_the_user_is_absent():
    progress = Progress(user_id=new_id())
    progress.record_workout(date(2026, 8, 1), 5, 30)

    progress.break_streak_if_missed(date(2026, 8, 2))
    assert progress.current_streak == 1

    progress.break_streak_if_missed(date(2026, 8, 5))
    assert progress.current_streak == 0
    assert progress.longest_streak == 1


def test_progress_aggregates_totals():
    progress = Progress(user_id=new_id())
    progress.record_workout(date(2026, 8, 1), 6, 40)
    progress.record_workout(date(2026, 8, 2), 4, 20)

    assert progress.total_exercises == 10
    assert progress.total_minutes == 60
    assert progress.average_workout_minutes == 30.0


def test_progress_reports_no_average_before_any_workout():
    assert Progress(user_id=new_id()).average_workout_minutes == 0.0


def test_a_workout_cannot_be_recorded_out_of_order():
    progress = Progress(user_id=new_id())
    progress.record_workout(date(2026, 8, 5), 5, 30)

    with pytest.raises(ValueError):
        progress.record_workout(date(2026, 8, 1), 5, 30)


def test_progress_rejects_negative_totals():
    with pytest.raises(ValueError):
        Progress(user_id=new_id(), total_workouts=-1)
