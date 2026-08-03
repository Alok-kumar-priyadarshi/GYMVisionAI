# file_name: test_repositories.py

"""Integration tests for the repository implementations.

These run against a real schema created from the real models, so mapping,
relationships, cascades and queries are all genuinely exercised. The database is
SQLite rather than PostgreSQL, because none is available here; the portable
column types mean the same mapping code runs against both.
"""

from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities.diet import DietPlan, Meal, MealItem
from app.domain.entities.exercise import ExerciseResult, ExerciseSession
from app.domain.entities.progress import Progress
from app.domain.entities.user import BodyProfile, User
from app.domain.entities.workout import WorkoutExercise, WorkoutPlan, WorkoutSession
from app.domain.value_objects.enums import DietPreference, MealType, SessionStatus
from app.domain.value_objects.identifier import new_id
from app.infrastructure.database import models  # noqa: F401 - registers tables
from app.infrastructure.database.session import Base, configure_database
from app.infrastructure.repositories.diet_repository import (
    SqlDietPlanRepository,
    SqlFoodRepository,
)
from app.infrastructure.repositories.exercise_repository import (
    SqlExerciseRepository,
    SqlExerciseSessionRepository,
)
from app.infrastructure.repositories.progress_repository import SqlProgressRepository
from app.infrastructure.repositories.user_repository import (
    SqlBodyProfileRepository,
    SqlUserRepository,
)
from app.infrastructure.repositories.workout_repository import (
    SqlWorkoutPlanRepository,
    SqlWorkoutSessionRepository,
)
from app.infrastructure.seed import seed_all


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = configure_database("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as active:
        await seed_all(active)
        await active.commit()
        yield active

    await engine.dispose()


@pytest_asyncio.fixture
async def user(session: AsyncSession) -> User:
    stored = await SqlUserRepository(session).add(
        User(google_id="google-1", email="alice@test.com", full_name="Alice")
    )
    await session.commit()
    return stored


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


async def test_a_user_round_trips(session, user):
    repository = SqlUserRepository(session)

    assert (await repository.get(user.id)).email == "alice@test.com"
    assert (await repository.get_by_google_id("google-1")).id == user.id
    assert (await repository.get_by_email("alice@test.com")).id == user.id
    assert await repository.exists(user.id) is True


async def test_an_absent_user_returns_none(session):
    repository = SqlUserRepository(session)

    assert await repository.get(new_id()) is None
    assert await repository.get_by_google_id("nobody") is None
    assert await repository.exists(new_id()) is False


async def test_a_user_can_be_updated(session, user):
    repository = SqlUserRepository(session)
    user.full_name = "Alice Updated"
    user.touch()

    updated = await repository.update(user)

    assert updated.full_name == "Alice Updated"
    assert (await repository.get(user.id)).full_name == "Alice Updated"


async def test_a_body_profile_round_trips(session, user):
    repository = SqlBodyProfileRepository(session)
    stored = await repository.add(
        BodyProfile(
            user_id=user.id,
            age=30,
            gender="Male",
            height_cm=178,
            weight_kg=78,
            fitness_goal="General Fitness",
            fitness_level="Intermediate",
            problem_areas=("belly",),
        )
    )

    fetched = await repository.get_for_user(user.id)

    assert fetched.id == stored.id
    assert fetched.problem_areas == ("belly",)
    assert str(fetched.fitness_goal) == "General Fitness"


async def test_a_body_profile_can_be_replaced(session, user):
    repository = SqlBodyProfileRepository(session)
    original = await repository.add(
        BodyProfile(
            user_id=user.id, age=30, gender="Male", height_cm=178, weight_kg=78,
            fitness_goal="General Fitness", fitness_level="Intermediate",
        )
    )

    await repository.update(
        BodyProfile(
            id=original.id, user_id=user.id, age=31, gender="Male", height_cm=178,
            weight_kg=74, fitness_goal="Muscle Gain", fitness_level="Advanced",
        )
    )

    fetched = await repository.get_for_user(user.id)
    assert fetched.weight_kg == 74
    assert str(fetched.fitness_goal) == "Muscle Gain"


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------


async def test_the_seeded_library_is_queryable(session):
    repository = SqlExerciseRepository(session)

    assert len(await repository.list_supported()) == 29
    assert (await repository.get_by_slug("push_ups")).name == "Push-ups"
    assert len(await repository.list_by_category("Core")) == 9


async def test_seeding_twice_refreshes_rather_than_duplicates(session):
    await seed_all(session)
    await session.commit()

    assert len(await SqlExerciseRepository(session).list_supported()) == 29
    assert len(await SqlFoodRepository(session).list_all()) == 36


async def test_seeding_preserves_identifiers(session):
    repository = SqlExerciseRepository(session)
    before = (await repository.get_by_slug("push_ups")).id

    await seed_all(session)
    await session.commit()

    assert (await repository.get_by_slug("push_ups")).id == before


async def test_an_exercise_session_round_trips(session, user):
    exercise = await SqlExerciseRepository(session).get_by_slug("push_ups")
    repository = SqlExerciseSessionRepository(session)

    stored = await repository.add(
        ExerciseSession(user_id=user.id, exercise_id=exercise.id)
    )

    assert (await repository.get(stored.id)).exercise_id == exercise.id
    assert (await repository.get_active_for_user(user.id)).id == stored.id


async def test_a_completed_session_is_no_longer_active(session, user):
    exercise = await SqlExerciseRepository(session).get_by_slug("push_ups")
    repository = SqlExerciseSessionRepository(session)
    stored = await repository.add(
        ExerciseSession(user_id=user.id, exercise_id=exercise.id)
    )

    stored.record(total_reps=12, duration_seconds=90)
    stored.complete(average_accuracy=0.95)
    await repository.update(stored)

    assert await repository.get_active_for_user(user.id) is None
    reloaded = await repository.get(stored.id)
    assert reloaded.total_reps == 12
    assert reloaded.status is SessionStatus.COMPLETED


async def test_detector_results_are_appended_and_read_back(session, user):
    exercise = await SqlExerciseRepository(session).get_by_slug("push_ups")
    repository = SqlExerciseSessionRepository(session)
    stored = await repository.add(
        ExerciseSession(user_id=user.id, exercise_id=exercise.id)
    )

    await repository.add_results(
        tuple(
            ExerciseResult(
                exercise_session_id=stored.id,
                frame_timestamp=float(index),
                rep_count=index,
                current_stage="up",
                feedback=("Good form",),
                metrics={"elbow_angle": 160 + index},
                confidence=0.9,
            )
            for index in range(3)
        )
    )

    results = await repository.list_results(stored.id)
    assert len(results) == 3
    assert results[0].frame_timestamp == 0.0
    assert results[2].metrics["elbow_angle"] == 162
    assert results[0].feedback == ("Good form",)


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------


async def build_plan(session, user) -> WorkoutPlan:
    exercises = await SqlExerciseRepository(session).list_supported()
    plan_id = new_id()
    return WorkoutPlan(
        id=plan_id,
        user_id=user.id,
        title="Full Body Balance",
        goal="General Fitness",
        difficulty="Beginner",
        estimated_duration_minutes=30,
        exercises=tuple(
            WorkoutExercise(
                workout_plan_id=plan_id,
                exercise_id=exercises[index].id,
                display_order=index + 1,
                sets=3,
                repetitions=12,
                rest_seconds=45,
            )
            for index in range(3)
        ),
    )


async def test_a_plan_persists_with_its_exercises(session, user):
    repository = SqlWorkoutPlanRepository(session)

    stored = await repository.add(await build_plan(session, user))
    reloaded = await repository.get(stored.id)

    assert reloaded.exercise_count == 3
    assert reloaded.total_sets == 9
    assert [item.display_order for item in reloaded.in_order()] == [1, 2, 3]


async def test_the_current_plan_is_the_newest(session, user):
    repository = SqlWorkoutPlanRepository(session)
    await repository.add(await build_plan(session, user))
    second = await repository.add(await build_plan(session, user))

    assert (await repository.get_current_for_user(user.id)).id == second.id
    assert await repository.count_for_user(user.id) == 2


async def test_an_archived_plan_is_not_current(session, user):
    repository = SqlWorkoutPlanRepository(session)
    stored = await repository.add(await build_plan(session, user))

    await repository.archive(stored.id)

    assert await repository.get_current_for_user(user.id) is None


async def test_deleting_a_plan_removes_its_exercises(session, user):
    repository = SqlWorkoutPlanRepository(session)
    stored = await repository.add(await build_plan(session, user))

    await repository.delete(stored.id)

    assert await repository.get(stored.id) is None
    assert await repository.count_for_user(user.id) == 0


async def test_a_workout_session_round_trips(session, user):
    plan = await SqlWorkoutPlanRepository(session).add(await build_plan(session, user))
    repository = SqlWorkoutSessionRepository(session)

    stored = await repository.add(
        WorkoutSession(user_id=user.id, workout_plan_id=plan.id)
    )
    stored.start()
    stored.complete(duration_seconds=1800, average_accuracy=0.9, calories_burned=210)
    await repository.update(stored)

    reloaded = await repository.get(stored.id)
    assert reloaded.is_completed is True
    assert reloaded.calories_burned == 210
    assert await repository.get_active_for_user(user.id) is None


# ---------------------------------------------------------------------------
# Diet
# ---------------------------------------------------------------------------


async def test_the_seeded_food_library_is_queryable(session):
    repository = SqlFoodRepository(session)

    assert len(await repository.list_all()) == 36
    assert (await repository.get_by_slug("paneer")).name == "Paneer"

    vegan_lunch = await repository.list_for_meal(MealType.LUNCH, DietPreference.VEGAN)
    assert vegan_lunch
    assert all(food.suits(DietPreference.VEGAN) for food in vegan_lunch)


async def test_a_diet_plan_persists_with_meals_and_portions(session, user):
    foods = await SqlFoodRepository(session).list_all()
    repository = SqlDietPlanRepository(session)

    plan_id = new_id()
    meal_id = new_id()
    stored = await repository.add(
        DietPlan(
            id=plan_id,
            user_id=user.id,
            goal="Weight Loss",
            diet_preference="Vegetarian",
            estimated_calories=1800,
            water_target_ml=2500,
            meals=(
                Meal(
                    id=meal_id,
                    diet_plan_id=plan_id,
                    meal_type="Breakfast",
                    display_order=1,
                    items=(
                        MealItem(meal_id=meal_id, food_id=foods[0].id, servings=0.75),
                    ),
                ),
            ),
        )
    )

    reloaded = await repository.get(stored.id)
    assert len(reloaded.meals) == 1
    assert reloaded.meal(MealType.BREAKFAST).items[0].servings == 0.75


async def test_activating_a_plan_archives_the_previous_one(session, user):
    repository = SqlDietPlanRepository(session)

    first = DietPlan(
        user_id=user.id, goal="Weight Loss", estimated_calories=1800,
        water_target_ml=2500,
    )
    first.activate()
    await repository.add(first)
    assert (await repository.get_active_for_user(user.id)).id == first.id

    await repository.archive_active(user.id)

    assert await repository.get_active_for_user(user.id) is None


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


async def test_progress_round_trips(session, user):
    repository = SqlProgressRepository(session)
    stored = await repository.add(Progress(user_id=user.id))

    stored.record_workout(date(2026, 8, 1), exercises_completed=6, duration_minutes=40)
    stored.record_workout(date(2026, 8, 2), exercises_completed=5, duration_minutes=35)
    await repository.update(stored)

    reloaded = await repository.get_for_user(user.id)
    assert reloaded.current_streak == 2
    assert reloaded.total_workouts == 2
    assert reloaded.total_minutes == 75
    assert reloaded.last_workout_date == date(2026, 8, 2)


async def test_absent_progress_returns_none(session):
    assert await SqlProgressRepository(session).get_for_user(new_id()) is None


async def test_updating_missing_progress_is_rejected(session, user):
    with pytest.raises(ValueError):
        await SqlProgressRepository(session).update(Progress(user_id=user.id))


# ---------------------------------------------------------------------------
# Startup seeding
# ---------------------------------------------------------------------------


async def test_an_empty_library_is_seeded_on_demand(session):
    """A migrated but unseeded database heals itself rather than failing later."""
    from sqlalchemy import delete

    from app.infrastructure.database.models import ExerciseModel, FoodModel
    from app.infrastructure.seed import seed_if_empty

    await session.execute(delete(ExerciseModel))
    await session.execute(delete(FoodModel))
    await session.commit()

    written = await seed_if_empty(session)

    assert written == {"exercises": 29, "foods": 36}
    assert len(await SqlExerciseRepository(session).list_supported()) == 29


async def test_a_populated_library_is_left_alone(session):
    from app.infrastructure.seed import seed_if_empty

    # Already seeded by the fixture, so nothing should be rewritten.
    assert await seed_if_empty(session) is None
