# file_name: diet.py

"""Diet domain entities.

``docs/04_backend/29_DOMAIN_MODEL.md``: a diet plan contains meals, and meals
reference foods. ``Food`` is read-only during runtime, per section 8.

The documented ``Meal`` to ``Food`` relationship carries no quantity, but a meal
without portions is not a usable recommendation, so ``MealItem`` records the
serving amount the Diet Planning Engine produced. This addition is recorded in
``docs/03_business/23_DIET_PLANNING_ENGINE.md``.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities.user import utc_now
from app.domain.value_objects.enums import (
    DietPlanStatus,
    DietPreference,
    FitnessGoal,
    FoodCategory,
    MealType,
)
from app.domain.value_objects.coercion import as_enum, as_enums
from app.domain.value_objects.identifier import new_id


@dataclass(frozen=True)
class Food:
    """One food item in the nutrition library.

    Frozen because section 8 makes food read-only during runtime.
    """

    slug: str
    name: str
    category: FoodCategory
    calories: float
    protein_g: float
    carbohydrates_g: float
    fat_g: float
    serving_size: str
    meal_types: tuple[MealType, ...] = ()
    diet_tags: tuple[DietPreference, ...] = ()
    id: UUID = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.calories <= 0:
            raise ValueError("a food requires positive calories")
        if min(self.protein_g, self.carbohydrates_g, self.fat_g) < 0:
            raise ValueError("macronutrients cannot be negative")

        object.__setattr__(self, "category", as_enum(self.category, FoodCategory))
        object.__setattr__(self, "meal_types", as_enums(self.meal_types, MealType))
        object.__setattr__(
            self, "diet_tags", as_enums(self.diet_tags, DietPreference)
        )

    def suits(self, preference: DietPreference) -> bool:
        """Report whether the food is allowed for a dietary preference."""
        return preference in self.diet_tags


@dataclass(frozen=True)
class MealItem:
    """One food and the amount of it prescribed in a meal."""

    meal_id: UUID
    food_id: UUID
    servings: float
    id: UUID = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.servings <= 0:
            raise ValueError("a meal item requires a positive serving amount")


@dataclass
class Meal:
    """One meal inside a diet plan."""

    diet_plan_id: UUID
    meal_type: MealType
    display_order: int
    items: tuple[MealItem, ...] = ()
    id: UUID = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.display_order < 1:
            raise ValueError("display order starts at 1")
        self.meal_type = as_enum(self.meal_type, MealType)
        self.items = tuple(self.items)

    @property
    def food_ids(self) -> tuple[UUID, ...]:
        """Return the foods this meal references."""
        return tuple(item.food_id for item in self.items)


@dataclass
class DietPlan:
    """A generated daily nutrition plan owned by one user."""

    user_id: UUID
    goal: FitnessGoal
    estimated_calories: int
    water_target_ml: int
    diet_preference: DietPreference = DietPreference.VEGETARIAN
    meals: tuple[Meal, ...] = ()
    status: DietPlanStatus = DietPlanStatus.GENERATED
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.estimated_calories <= 0:
            raise ValueError("a diet plan requires a positive calorie estimate")
        if self.water_target_ml <= 0:
            raise ValueError("a diet plan requires a positive water target")

        self.goal = as_enum(self.goal, FitnessGoal)
        self.diet_preference = as_enum(self.diet_preference, DietPreference)
        self.status = as_enum(self.status, DietPlanStatus)
        self.meals = tuple(self.meals)
        orders = [meal.display_order for meal in self.meals]
        if len(set(orders)) != len(orders):
            raise ValueError("two meals share a display order")

    def activate(self) -> None:
        """Make this the user's current plan."""
        self.status = DietPlanStatus.ACTIVE
        self.touch()

    def archive(self) -> None:
        """Retire the plan, keeping it for history."""
        self.status = DietPlanStatus.ARCHIVED
        self.touch()

    def meal(self, meal_type: MealType) -> Meal | None:
        """Return one meal of the day, or ``None`` if it is not planned."""
        for item in self.meals:
            if item.meal_type == meal_type:
                return item
        return None

    def in_order(self) -> tuple[Meal, ...]:
        """Return the meals sorted by the order they are eaten."""
        return tuple(sorted(self.meals, key=lambda item: item.display_order))

    def touch(self) -> None:
        """Record that the entity changed."""
        self.updated_at = utc_now()
