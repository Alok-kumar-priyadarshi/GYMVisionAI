# file_name: diet_repository.py

"""Repository interfaces for the diet domain."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.diet import DietPlan, Food
from app.domain.value_objects.enums import DietPreference, MealType


class FoodRepository(ABC):
    """Persistence for the ``Food`` aggregate.

    Food is read-only at runtime, so the library changes only by re-seeding from
    configuration.
    """

    @abstractmethod
    async def get(self, food_id: UUID) -> Food | None:
        """Return a food by identifier, or ``None`` if absent."""

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Food | None:
        """Return a food by slug, or ``None`` if absent."""

    @abstractmethod
    async def list_all(self) -> tuple[Food, ...]:
        """Return the whole food library."""

    @abstractmethod
    async def list_for_meal(
        self, meal_type: MealType, preference: DietPreference
    ) -> tuple[Food, ...]:
        """Return foods suitable for one meal and dietary preference."""

    @abstractmethod
    async def upsert_many(self, foods: tuple[Food, ...]) -> int:
        """Seed or refresh the library from configuration.

        Returns:
            The number of foods written.
        """


class DietPlanRepository(ABC):
    """Persistence for the ``DietPlan`` aggregate, including its meals."""

    @abstractmethod
    async def get(self, plan_id: UUID) -> DietPlan | None:
        """Return a plan by identifier, or ``None`` if absent."""

    @abstractmethod
    async def get_active_for_user(self, user_id: UUID) -> DietPlan | None:
        """Return a user's active plan, or ``None`` if none is active."""

    @abstractmethod
    async def list_for_user(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> tuple[DietPlan, ...]:
        """Return a user's plans, newest first."""

    @abstractmethod
    async def count_for_user(self, user_id: UUID) -> int:
        """Return how many plans a user has, for pagination totals."""

    @abstractmethod
    async def add(self, plan: DietPlan) -> DietPlan:
        """Persist a plan with its meals and portions in one transaction."""

    @abstractmethod
    async def archive_active(self, user_id: UUID) -> None:
        """Retire a user's current plan before a new one becomes active."""
