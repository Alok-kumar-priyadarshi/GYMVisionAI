# file_name: diet_repository.py

"""SQLAlchemy implementations of the diet repositories."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.diet import DietPlan, Food
from app.domain.repositories.diet_repository import DietPlanRepository, FoodRepository
from app.domain.value_objects.enums import DietPlanStatus, DietPreference, MealType
from app.infrastructure.database import mappers
from app.infrastructure.database.models import DietPlanModel, FoodModel


class SqlFoodRepository(FoodRepository):
    """Stores the food library in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, food_id: UUID) -> Food | None:
        model = await self._session.get(FoodModel, food_id)
        return mappers.to_food(model) if model else None

    async def get_by_slug(self, slug: str) -> Food | None:
        result = await self._session.execute(
            select(FoodModel).where(FoodModel.slug == slug)
        )
        model = result.scalar_one_or_none()
        return mappers.to_food(model) if model else None

    async def list_all(self) -> tuple[Food, ...]:
        result = await self._session.execute(
            select(FoodModel).order_by(FoodModel.category, FoodModel.name)
        )
        return tuple(mappers.to_food(model) for model in result.scalars())

    async def list_for_meal(
        self, meal_type: MealType, preference: DietPreference
    ) -> tuple[Food, ...]:
        """Return foods for one meal and preference.

        Meal types and diet tags are stored as JSON lists, whose containment
        operators differ between PostgreSQL and SQLite. Filtering happens in
        Python so the query stays portable; the food library is small and fully
        cached by the Food Catalog Engine, so this costs nothing meaningful.
        """
        foods = await self.list_all()
        return tuple(
            food
            for food in foods
            if food.suits(preference) and meal_type in food.meal_types
        )

    async def upsert_many(self, foods: tuple[Food, ...]) -> int:
        """Seed or refresh the library, matching on the stable slug."""
        written = 0
        for entity in foods:
            result = await self._session.execute(
                select(FoodModel).where(FoodModel.slug == entity.slug)
            )
            model = result.scalar_one_or_none()

            if model is None:
                self._session.add(mappers.to_food_model(entity))
            else:
                refreshed = mappers.to_food_model(entity)
                model.name = refreshed.name
                model.category = refreshed.category
                model.calories = refreshed.calories
                model.protein_g = refreshed.protein_g
                model.carbohydrates_g = refreshed.carbohydrates_g
                model.fat_g = refreshed.fat_g
                model.serving_size = refreshed.serving_size
                model.meal_types = refreshed.meal_types
                model.diet_tags = refreshed.diet_tags
            written += 1

        await self._session.flush()
        return written


class SqlDietPlanRepository(DietPlanRepository):
    """Stores diet plans, their meals and portions in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, plan_id: UUID) -> DietPlan | None:
        model = await self._session.get(DietPlanModel, plan_id)
        return mappers.to_diet_plan(model) if model else None

    async def get_active_for_user(self, user_id: UUID) -> DietPlan | None:
        # Matched on "not archived" rather than on ACTIVE. A plan is stored with
        # status GENERATED, so an equality test against ACTIVE never matched the
        # plan that had just been created and the user's current plan read back
        # as absent.
        result = await self._session.execute(
            select(DietPlanModel)
            .where(
                DietPlanModel.user_id == user_id,
                DietPlanModel.status != str(DietPlanStatus.ARCHIVED),
            )
            .order_by(DietPlanModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return mappers.to_diet_plan(model) if model else None

    async def count_for_user(self, user_id: UUID) -> int:
        total = await self._session.scalar(
            select(func.count())
            .select_from(DietPlanModel)
            .where(DietPlanModel.user_id == user_id)
        )
        return int(total or 0)

    async def list_for_user(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> tuple[DietPlan, ...]:
        result = await self._session.execute(
            select(DietPlanModel)
            .where(DietPlanModel.user_id == user_id)
            .order_by(DietPlanModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return tuple(mappers.to_diet_plan(model) for model in result.scalars())

    async def add(self, plan: DietPlan) -> DietPlan:
        model = mappers.to_diet_plan_model(plan)
        self._session.add(model)
        await self._session.flush()
        return mappers.to_diet_plan(model)

    async def archive_active(self, user_id: UUID) -> None:
        # Same reasoning as `get_active_for_user`: a stored plan is GENERATED,
        # so archiving only ACTIVE rows left every previous plan current.
        result = await self._session.execute(
            select(DietPlanModel).where(
                DietPlanModel.user_id == user_id,
                DietPlanModel.status != str(DietPlanStatus.ARCHIVED),
            )
        )
        for model in result.scalars():
            model.status = str(DietPlanStatus.ARCHIVED)
        await self._session.flush()
