# file_name: diet.py

"""Diet endpoints.

Implements ``contracts/diet/01_GENERATE_DIET_PLAN.md`` through
``contracts/diet/04_GET_DIET_PLAN.md``.

Generation is deterministic and never uses AI, per
``docs/03_business/23_DIET_PLANNING_ENGINE.md`` section 18.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.application.services.diet_service import DietService
from app.core.dependencies import CurrentUser, get_diet_service, get_food_repository
from app.domain.entities.diet import DietPlan, Food
from app.domain.repositories.diet_repository import FoodRepository
from app.schemas.dto import (
    DietPlanResponse,
    DietPlanSummaryResponse,
    DietTotalsResponse,
    GenerateDietRequest,
    MealItemResponse,
    MealResponse,
)
from app.schemas.response import success

router = APIRouter()

ServiceDep = Annotated[DietService, Depends(get_diet_service)]
FoodsDep = Annotated[FoodRepository, Depends(get_food_repository)]


def to_summary(plan: DietPlan) -> DietPlanSummaryResponse:
    """Shape a plan for a listing."""
    return DietPlanSummaryResponse(
        diet_plan_id=str(plan.id),
        goal=str(plan.goal),
        diet_preference=str(plan.diet_preference),
        estimated_calories=plan.estimated_calories,
        water_target_ml=plan.water_target_ml,
        status=str(plan.status),
        meal_count=len(plan.meals),
        created_at=plan.created_at,
    )


def to_detail(plan: DietPlan, foods: dict[UUID, Food]) -> DietPlanResponse:
    """Shape a plan and resolve the foods its portions reference.

    Nutrition is reported for the portion as served rather than per serving, so
    the client never multiplies anything to render a meal, and the totals row
    cannot disagree with the items above it.
    """
    meals: list[MealResponse] = []
    calories = protein = carbohydrates = fat = 0.0

    for meal in sorted(plan.meals, key=lambda item: item.display_order):
        items: list[MealItemResponse] = []
        meal_calories = 0.0

        for entry in meal.items:
            food = foods.get(entry.food_id)
            if food is None:
                # A plan referencing a food no longer in the library is still
                # worth showing; dropping the row is better than failing the
                # whole page.
                continue

            served_calories = round(food.calories * entry.servings, 1)
            served_protein = round(food.protein_g * entry.servings, 1)
            served_carbohydrates = round(food.carbohydrates_g * entry.servings, 1)
            served_fat = round(food.fat_g * entry.servings, 1)

            items.append(
                MealItemResponse(
                    food_id=str(food.id),
                    slug=food.slug,
                    name=food.name,
                    category=str(food.category),
                    servings=entry.servings,
                    serving_size=food.serving_size,
                    calories=served_calories,
                    protein_g=served_protein,
                    carbohydrates_g=served_carbohydrates,
                    fat_g=served_fat,
                )
            )

            meal_calories += served_calories
            calories += served_calories
            protein += served_protein
            carbohydrates += served_carbohydrates
            fat += served_fat

        meals.append(
            MealResponse(
                meal_id=str(meal.id),
                meal_type=str(meal.meal_type),
                display_order=meal.display_order,
                name=str(meal.meal_type),
                target_calories=round(meal_calories),
                items=items,
            )
        )

    return DietPlanResponse(
        **to_summary(plan).model_dump(),
        meals=meals,
        totals=DietTotalsResponse(
            calories=round(calories, 1),
            protein_g=round(protein, 1),
            carbohydrates_g=round(carbohydrates, 1),
            fat_g=round(fat, 1),
        ),
    )


async def _foods_by_id(foods: FoodRepository) -> dict[UUID, Food]:
    """Index the catalog so a plan's portions resolve without a query each."""
    return {food.id: food for food in await foods.list_all()}


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    summary="Generate a diet plan",
)
async def generate_diet_plan(
    user: CurrentUser,
    service: ServiceDep,
    foods: FoodsDep,
    payload: GenerateDietRequest | None = None,
) -> dict[str, Any]:
    """Generate and persist a diet plan from the user's profile.

    Raises:
        ProfileNotFoundError: If the user has no body profile.
        FoodLibraryUnavailableError: If the food catalog is empty.
        DietPlanGenerationError: If no plan can be produced.
    """
    plan = await service.generate(
        user.id, diet_preference=payload.diet_preference if payload else None
    )
    detail = to_detail(plan, await _foods_by_id(foods))
    return success(
        "Diet plan generated successfully.", detail.model_dump(by_alias=True)
    )


@router.get("/current", summary="Get the user's current diet plan")
async def get_current_diet_plan(
    user: CurrentUser, service: ServiceDep, foods: FoodsDep
) -> dict[str, Any]:
    """Return the user's active plan.

    Raises:
        DietPlanNotFoundError: If the user has generated none.
    """
    plan = await service.current(user.id)
    detail = to_detail(plan, await _foods_by_id(foods))
    return success(
        "Current diet plan retrieved successfully.", detail.model_dump(by_alias=True)
    )


@router.get("/history", summary="List the user's diet plans")
async def get_diet_plan_history(
    user: CurrentUser,
    service: ServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    """Return the user's plans, newest first."""
    offset = (page - 1) * limit
    stored = await service.history(user.id, limit=limit, offset=offset)
    total = await service.count(user.id)

    payload = success(
        "Diet plan history retrieved successfully.",
        [to_summary(plan).model_dump(by_alias=True) for plan in stored],
    )
    payload["pagination"] = {
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit if limit else 0,
    }
    return payload


@router.get("/{diet_plan_id}", summary="Get one diet plan")
async def get_diet_plan(
    diet_plan_id: UUID,
    user: CurrentUser,
    service: ServiceDep,
    foods: FoodsDep,
) -> dict[str, Any]:
    """Return one of the user's plans, active or archived.

    Raises:
        DietPlanNotFoundError: If it does not exist or belongs to someone else.
    """
    plan = await service.get(user.id, diet_plan_id)
    detail = to_detail(plan, await _foods_by_id(foods))
    return success(
        "Diet plan retrieved successfully.", detail.model_dump(by_alias=True)
    )
