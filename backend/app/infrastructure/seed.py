# file_name: seed.py

"""Seeds the database from configuration.

The exercise and food libraries are configuration-driven, so the database is a
projection of ``backend/configuration`` rather than an independent source of
truth. Seeding is idempotent: it matches on the stable slug, so running it twice
refreshes rather than duplicates, and identifiers already referenced by user data
stay valid.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.diet import Food
from app.domain.entities.exercise import Exercise
from app.infrastructure.database.models import ExerciseModel, FoodModel
from app.engines.exercise.catalog import load_exercise_registry
from app.engines.nutrition import load_food_registry
from app.infrastructure.repositories.diet_repository import SqlFoodRepository
from app.infrastructure.repositories.exercise_repository import SqlExerciseRepository

logger = logging.getLogger(__name__)


async def seed_exercises(session: AsyncSession) -> int:
    """Write the configured exercise library into the database."""
    registry = load_exercise_registry()
    exercises = tuple(
        Exercise(
            slug=definition.slug,
            name=definition.name,
            category=definition.category,
            difficulty=definition.difficulty,
            exercise_type=definition.exercise_type,
            movement_type=definition.movement_type,
            equipment=definition.equipment,
            primary_muscles=definition.primary_muscles,
            secondary_muscles=definition.secondary_muscles,
            instructions=definition.instructions,
            is_supported=True,
        )
        for definition in registry.all()
    )

    written = await SqlExerciseRepository(session).upsert_many(exercises)
    logger.info("Seeded %d exercises.", written)
    return written


async def seed_foods(session: AsyncSession) -> int:
    """Write the configured food library into the database."""
    registry = load_food_registry()
    foods = tuple(
        Food(
            slug=definition.slug,
            name=definition.name,
            category=definition.category,
            calories=definition.calories,
            protein_g=definition.protein_g,
            carbohydrates_g=definition.carbohydrates_g,
            fat_g=definition.fat_g,
            serving_size=definition.serving_size,
            meal_types=definition.meal_types,
            diet_tags=definition.diet_tags,
        )
        for definition in registry.all()
    )

    written = await SqlFoodRepository(session).upsert_many(foods)
    logger.info("Seeded %d foods.", written)
    return written


async def seed_all(session: AsyncSession) -> dict[str, int]:
    """Seed every configuration-driven library.

    Returns:
        How many rows were written per library.
    """
    return {
        "exercises": await seed_exercises(session),
        "foods": await seed_foods(session),
    }


async def seed_if_empty(session: AsyncSession) -> dict[str, int] | None:
    """Populate the libraries when the database has none.

    The exercise and food tables are a projection of ``backend/configuration``,
    not user data, so an empty table means the deployment was migrated but never
    seeded. Left alone, that surfaces much later as "exercise is missing from
    the library" when a workout is generated, which says nothing about the real
    cause.

    Returns:
        How many rows were written, or ``None`` if the libraries already exist.
    """
    exercises = await session.scalar(select(func.count()).select_from(ExerciseModel))
    foods = await session.scalar(select(func.count()).select_from(FoodModel))

    if exercises and foods:
        return None

    logger.warning(
        "Exercise or food library is empty; seeding from configuration."
    )
    written = await seed_all(session)
    await session.commit()
    return written
