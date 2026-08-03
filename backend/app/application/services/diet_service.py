# file_name: diet_service.py

"""Diet plan use cases.

Implements ``contracts/diet/01_GENERATE_DIET_PLAN.md`` through
``contracts/diet/04_GET_DIET_PLAN.md``.

Generation is deterministic and never uses AI. ``docs/03_business/
23_DIET_PLANNING_ENGINE.md`` section 18 forbids using Groq to generate diets;
the AI Coach may explain a plan it is given, but never authors one. Every
nutrition figure a user sees is therefore traceable to configuration rather than
to model output, which matters more here than anywhere else in the product.
"""

import logging
from uuid import UUID

from app.domain.entities.diet import DietPlan, Meal, MealItem
from app.domain.entities.user import BodyProfile
from app.domain.repositories.diet_repository import (
    DietPlanRepository,
    FoodRepository,
)
from app.domain.repositories.user_repository import BodyProfileRepository
from app.domain.value_objects.enums import DietPreference
from app.domain.value_objects.identifier import new_id
from app.engines.nutrition import build_diet_planner
from app.engines.nutrition.body_profile import BodyProfile as EngineBodyProfile
from app.shared.exceptions import (
    DietPlanGenerationError,
    DietPlanNotFoundError,
    FoodLibraryUnavailableError,
    ProfileNotFoundError,
)

logger = logging.getLogger(__name__)


class DietService:
    """Generates, stores and reads diet plans."""

    def __init__(
        self,
        plans: DietPlanRepository,
        foods: FoodRepository,
        profiles: BodyProfileRepository,
    ) -> None:
        self._plans = plans
        self._foods = foods
        self._profiles = profiles

    async def generate(
        self, user_id: UUID, diet_preference: DietPreference | None = None
    ) -> DietPlan:
        """Build a plan from the user's profile and store it.

        Args:
            user_id: Whose plan to build.
            diet_preference: Dietary preference to respect. When omitted the
                preference of the user's most recent plan is reused, so
                regenerating never silently changes a choice they already made.

        Raises:
            ProfileNotFoundError: If the user has no body profile.
            FoodLibraryUnavailableError: If the food catalog is empty.
            DietPlanGenerationError: If no plan can be produced.
        """
        profile = await self._profiles.get_for_user(user_id)
        if profile is None:
            raise ProfileNotFoundError()

        # A migrated but unseeded database would otherwise fail deep inside the
        # planner, naming a food slug and saying nothing about the real cause.
        catalogue = await self._foods.list_all()
        if not catalogue:
            raise FoodLibraryUnavailableError(
                "The food library is empty. Run 'python -m app.cli seed' to "
                "load it from configuration."
            )

        if diet_preference is None:
            diet_preference = await self._previous_preference(user_id)

        try:
            planned = build_diet_planner().generate(
                _to_engine_profile(profile, diet_preference)
            )
        except Exception as error:
            logger.exception("Diet plan generation failed.")
            raise DietPlanGenerationError() from error

        if not planned.meals:
            raise DietPlanGenerationError("The generated plan had no meals.")

        by_slug = {food.slug: food for food in catalogue}
        plan_id = new_id()
        meals: list[Meal] = []

        for planned_meal in planned.meals:
            meal_id = new_id()
            items: list[MealItem] = []

            for portion in planned_meal.portions:
                food = by_slug.get(portion.food.slug)
                if food is None:
                    # The engine works from configuration and the database is
                    # seeded from the same files, so this means the two have
                    # drifted apart rather than that one food is missing.
                    raise DietPlanGenerationError(
                        f"Food '{portion.food.slug}' is missing from the library."
                    )
                items.append(
                    MealItem(
                        meal_id=meal_id,
                        food_id=food.id,
                        servings=portion.servings,
                    )
                )

            meals.append(
                Meal(
                    id=meal_id,
                    diet_plan_id=plan_id,
                    meal_type=planned_meal.meal_type,
                    display_order=planned_meal.display_order,
                    items=tuple(items),
                )
            )

        # Only once the new plan is known to be buildable, so a failure never
        # leaves the user with nothing where they previously had a plan.
        await self._plans.archive_active(user_id)

        stored = await self._plans.add(
            DietPlan(
                id=plan_id,
                user_id=user_id,
                goal=planned.goal,
                estimated_calories=planned.target_calories,
                water_target_ml=planned.water_target_ml,
                diet_preference=planned.diet_preference,
                meals=tuple(meals),
            )
        )
        logger.info("Diet plan generated: %s", stored.id)
        return stored

    async def _previous_preference(self, user_id: UUID) -> DietPreference | None:
        """Return the preference of the user's most recent plan, if any."""
        recent = await self._plans.list_for_user(user_id, limit=1, offset=0)
        return recent[0].diet_preference if recent else None

    async def current(self, user_id: UUID) -> DietPlan:
        """Return the user's active plan.

        Raises:
            DietPlanNotFoundError: If the user has never generated one.
        """
        plan = await self._plans.get_active_for_user(user_id)
        if plan is None:
            raise DietPlanNotFoundError("No current diet plan.")
        return plan

    async def get(self, user_id: UUID, plan_id: UUID) -> DietPlan:
        """Return one of the user's plans, active or archived.

        Raises:
            DietPlanNotFoundError: If it does not exist or belongs to someone
                else.
        """
        plan = await self._plans.get(plan_id)
        if plan is None or plan.user_id != user_id:
            raise DietPlanNotFoundError()
        return plan

    async def history(
        self, user_id: UUID, limit: int, offset: int
    ) -> tuple[DietPlan, ...]:
        """Return the user's plans, newest first."""
        return await self._plans.list_for_user(user_id, limit=limit, offset=offset)

    async def count(self, user_id: UUID) -> int:
        """Return how many plans the user has, for pagination totals."""
        return await self._plans.count_for_user(user_id)


def _to_engine_profile(
    profile: BodyProfile, diet_preference: DietPreference | None
) -> EngineBodyProfile:
    """Project a stored body profile onto the planner's input contract.

    `29_DOMAIN_MODEL.md` gives `BodyProfile` no dietary preference, so that one
    value is supplied by the caller rather than read from the profile. See
    `contracts/diet/01_GENERATE_DIET_PLAN.md` section 5.
    """
    fields = {
        "age": profile.age,
        "gender": profile.gender,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "goal": profile.fitness_goal,
        "fitness_level": profile.fitness_level,
    }
    if diet_preference is not None:
        fields["diet_preference"] = diet_preference
    return EngineBodyProfile(**fields)
