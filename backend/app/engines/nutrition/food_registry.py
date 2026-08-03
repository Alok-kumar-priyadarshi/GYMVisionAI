# file_name: food_registry.py

"""In-memory catalogue of foods and meal templates.

Implements the Registry, Cache Manager, Search Service and Filter Service
components of ``docs/03_business/24_FOOD_CATALOG_ENGINE.md``.

The registry is built once during startup and read-only afterwards. Lookups are
dictionary based and therefore constant time, meeting the runtime target in
section 16.

The engine never generates diet plans or recommends meals. It only publishes
validated catalogue data.
"""

import logging
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from app.engines.nutrition.food_definition import (
    DietPreference,
    FoodCategory,
    FoodDefinition,
    MealType,
)
from app.engines.nutrition.food_loader import FoodLoader
from app.engines.nutrition.meal_template import MealTemplate
from app.engines.workout.workout_profile import FitnessGoal
from app.shared.exceptions import FoodNotFoundError, NutritionConfigurationError

logger = logging.getLogger(__name__)


class FoodRegistry:
    """Read-only catalogue of foods and meal templates."""

    def __init__(
        self,
        foods: tuple[FoodDefinition, ...],
        meal_templates: tuple[MealTemplate, ...] = (),
    ) -> None:
        """Build the catalogue and its lookup indexes."""
        self._foods = tuple(foods)
        self._templates = tuple(meal_templates)
        self._by_id: Mapping[str, FoodDefinition] = MappingProxyType(
            {food.id: food for food in self._foods}
        )
        self._by_slug: Mapping[str, FoodDefinition] = MappingProxyType(
            {food.slug: food for food in self._foods}
        )
        self._template_by_id: Mapping[str, MealTemplate] = MappingProxyType(
            {template.id: template for template in self._templates}
        )
        logger.info(
            "Food catalogue initialised with %d foods and %d meal templates.",
            len(self._foods),
            len(self._templates),
        )

    def __len__(self) -> int:
        return len(self._foods)

    def __contains__(self, food_id: str) -> bool:
        return food_id in self._by_id

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def all(self) -> tuple[FoodDefinition, ...]:
        """Return every food, ordered by identifier."""
        return self._foods

    def meal_templates(self) -> tuple[MealTemplate, ...]:
        """Return every meal template, ordered by identifier."""
        return self._templates

    def get(self, food_id: str) -> FoodDefinition:
        """Return one food by identifier.

        Raises:
            FoodNotFoundError: If no food has that identifier.
        """
        try:
            return self._by_id[food_id]
        except KeyError as error:
            raise FoodNotFoundError(f"Food '{food_id}' not found.") from error

    def get_by_slug(self, slug: str) -> FoodDefinition:
        """Return one food by slug.

        Raises:
            FoodNotFoundError: If no food has that slug.
        """
        try:
            return self._by_slug[slug]
        except KeyError as error:
            raise FoodNotFoundError(f"Food '{slug}' not found.") from error

    def template(self, template_id: str) -> MealTemplate:
        """Return one meal template by identifier.

        Raises:
            FoodNotFoundError: If no template has that identifier.
        """
        try:
            return self._template_by_id[template_id]
        except KeyError as error:
            raise FoodNotFoundError(
                f"Meal template '{template_id}' not found."
            ) from error

    def foods_in(self, template: MealTemplate) -> tuple[FoodDefinition, ...]:
        """Resolve a template's food references into food definitions."""
        return tuple(self.get(food_id) for food_id in template.food_ids)

    # ------------------------------------------------------------------
    # Search and filter
    # ------------------------------------------------------------------

    def search(self, query: str) -> tuple[FoodDefinition, ...]:
        """Return foods matching a free-text query.

        Searches the fields listed in section 12: name, category, meal type and
        dietary preference.

        Args:
            query: Case-insensitive search term. A blank query matches nothing.
        """
        term = query.strip().lower()
        if not term:
            return ()

        return tuple(
            food for food in self._foods if term in self._searchable_text(food)
        )

    def filter(
        self,
        *,
        category: FoodCategory | None = None,
        meal_type: MealType | None = None,
        diet_preference: DietPreference | None = None,
    ) -> tuple[FoodDefinition, ...]:
        """Return foods matching every supplied filter.

        Filters combine with AND. Omitted filters are ignored.
        """
        results = self._foods

        if category is not None:
            results = tuple(food for food in results if food.category == category)
        if meal_type is not None:
            results = tuple(food for food in results if food.served_at(meal_type))
        if diet_preference is not None:
            results = tuple(food for food in results if food.suits(diet_preference))
        return results

    def templates_for(
        self,
        *,
        meal_type: MealType | None = None,
        diet_preference: DietPreference | None = None,
        goal: FitnessGoal | None = None,
    ) -> tuple[MealTemplate, ...]:
        """Return meal templates matching every supplied filter."""
        results = self._templates

        if meal_type is not None:
            results = tuple(item for item in results if item.meal_type == meal_type)
        if diet_preference is not None:
            results = tuple(
                item for item in results if item.diet_preference == diet_preference
            )
        if goal is not None:
            results = tuple(item for item in results if item.suits(goal))
        return results

    @staticmethod
    def _searchable_text(food: FoodDefinition) -> str:
        """Return the lower-cased text a search query is matched against."""
        parts = (
            food.id,
            food.slug,
            food.name,
            food.category,
            *food.meal_types,
            *food.diet_tags,
        )
        return " ".join(parts).lower()


def build_food_registry(configuration_directory: Path | None = None) -> FoodRegistry:
    """Load configuration and build the catalogue, validating every reference.

    Args:
        configuration_directory: Root of the nutrition configuration. Defaults
            to the project's configuration directory.

    Returns:
        A registry containing every food and meal template.

    Raises:
        NutritionConfigurationError: If configuration is invalid or a template
            references a food that does not exist or does not fit the meal.
    """
    loader = FoodLoader(configuration_directory)
    registry = FoodRegistry(loader.load_foods(), loader.load_meal_templates())
    _verify_template_references(registry)
    return registry


@lru_cache(maxsize=1)
def load_food_registry() -> FoodRegistry:
    """Return the application's food catalogue, building it on first use."""
    return build_food_registry()


def _verify_template_references(registry: FoodRegistry) -> None:
    """Fail startup when a meal template references food it should not.

    Section 13 requires templates to reference existing foods. A reference is
    also rejected when the food does not belong to the template's meal or does
    not suit its dietary preference, because such a template could never be
    served as written.
    """
    for template in registry.meal_templates():
        for food_id in template.food_ids:
            if food_id not in registry:
                raise NutritionConfigurationError(
                    f"Meal template '{template.id}' references unknown food "
                    f"'{food_id}'."
                )

            food = registry.get(food_id)
            if not food.served_at(template.meal_type):
                raise NutritionConfigurationError(
                    f"Meal template '{template.id}' uses '{food.name}', which is "
                    f"not served at {template.meal_type}."
                )
            if not food.suits(template.diet_preference):
                raise NutritionConfigurationError(
                    f"Meal template '{template.id}' uses '{food.name}', which is "
                    f"not {template.diet_preference}."
                )
