# file_name: diet_plan.py

"""Output contract of the Diet Planning Engine.

``DietPlan`` carries the contents listed in
``docs/03_business/23_DIET_PLANNING_ENGINE.md`` section 5: the five daily meals,
water intake and estimated calories. Plans are immutable once generated.

The plan is a runtime contract, not a database model. It maps onto the
``DietPlan``, ``Meal`` and ``Food`` entities in
``docs/04_backend/29_DOMAIN_MODEL.md``.

One mapping gap is worth recording. ``MealPortion.servings`` has no home on the
documented domain model, whose ``Meal`` to ``Food`` relationship carries no
quantity. Persisting a plan will need that quantity, because a meal without
portions is not a usable recommendation.
"""

from dataclasses import dataclass
from typing import Any

from app.engines.nutrition.food_definition import (
    DietPreference,
    FoodDefinition,
    MealType,
)
from app.engines.workout.workout_profile import FitnessGoal


@dataclass(frozen=True, slots=True)
class MealPortion:
    """One food and how much of it to eat.

    Attributes:
        food: The catalogued food.
        servings: Multiples of the food's configured serving size.
    """

    food: FoodDefinition
    servings: float

    @property
    def calories(self) -> float:
        """Return the energy of this portion, in kcal."""
        return round(self.food.calories * self.servings, 1)

    @property
    def protein_g(self) -> float:
        """Return the protein of this portion, in grams."""
        return round(self.food.protein_g * self.servings, 1)

    @property
    def carbohydrates_g(self) -> float:
        """Return the carbohydrate of this portion, in grams."""
        return round(self.food.carbohydrates_g * self.servings, 1)

    @property
    def fat_g(self) -> float:
        """Return the fat of this portion, in grams."""
        return round(self.food.fat_g * self.servings, 1)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the portion."""
        return {
            "food_id": self.food.id,
            "slug": self.food.slug,
            "name": self.food.name,
            "serving_size": self.food.serving_size,
            "servings": self.servings,
            "calories": self.calories,
            "protein_g": self.protein_g,
            "carbohydrates_g": self.carbohydrates_g,
            "fat_g": self.fat_g,
        }


@dataclass(frozen=True, slots=True)
class PlannedMeal:
    """One meal of the day.

    Attributes:
        meal_type: Which meal of the day this is.
        display_order: Position in the day, starting at 1.
        name: Display name, taken from the meal template used.
        template_id: The meal template the meal was built from.
        portions: The foods and amounts making up the meal.
        target_calories: Calories the meal was scaled towards.
    """

    meal_type: MealType
    display_order: int
    name: str
    template_id: str
    portions: tuple[MealPortion, ...]
    target_calories: int

    @property
    def calories(self) -> float:
        """Return the meal's total energy, in kcal."""
        return round(sum(portion.calories for portion in self.portions), 1)

    @property
    def protein_g(self) -> float:
        """Return the meal's total protein, in grams."""
        return round(sum(portion.protein_g for portion in self.portions), 1)

    @property
    def carbohydrates_g(self) -> float:
        """Return the meal's total carbohydrate, in grams."""
        return round(sum(portion.carbohydrates_g for portion in self.portions), 1)

    @property
    def fat_g(self) -> float:
        """Return the meal's total fat, in grams."""
        return round(sum(portion.fat_g for portion in self.portions), 1)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the meal."""
        return {
            "meal_type": str(self.meal_type),
            "display_order": self.display_order,
            "name": self.name,
            "template_id": self.template_id,
            "target_calories": self.target_calories,
            "calories": self.calories,
            "protein_g": self.protein_g,
            "carbohydrates_g": self.carbohydrates_g,
            "fat_g": self.fat_g,
            "portions": [portion.to_dict() for portion in self.portions],
        }


@dataclass(frozen=True, slots=True)
class DietPlan:
    """A complete daily eating plan.

    Attributes:
        goal: The goal the plan was generated for.
        diet_preference: The dietary preference the plan respects.
        target_calories: The estimated daily calorie target.
        water_target_ml: Suggested daily water intake, in millilitres.
        meals: The day's meals, in the order they are eaten.

    The calorie target is an estimate used to guide meal selection. It is not
    medical advice, per section 10.
    """

    goal: FitnessGoal
    diet_preference: DietPreference
    target_calories: int
    water_target_ml: int
    meals: tuple[PlannedMeal, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.meals, tuple):
            object.__setattr__(self, "meals", tuple(self.meals))

    def __len__(self) -> int:
        return len(self.meals)

    @property
    def estimated_calories(self) -> float:
        """Return the plan's actual energy, in kcal."""
        return round(sum(meal.calories for meal in self.meals), 1)

    @property
    def protein_g(self) -> float:
        """Return the plan's total protein, in grams."""
        return round(sum(meal.protein_g for meal in self.meals), 1)

    @property
    def carbohydrates_g(self) -> float:
        """Return the plan's total carbohydrate, in grams."""
        return round(sum(meal.carbohydrates_g for meal in self.meals), 1)

    @property
    def fat_g(self) -> float:
        """Return the plan's total fat, in grams."""
        return round(sum(meal.fat_g for meal in self.meals), 1)

    def meal(self, meal_type: MealType | str) -> PlannedMeal | None:
        """Return one meal of the day, or ``None`` if it is not planned.

        Accepts the enum or its string value, since ``MealType`` is a ``StrEnum``.
        """
        for item in self.meals:
            if item.meal_type == meal_type:
                return item
        return None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the plan."""
        return {
            "goal": str(self.goal),
            "diet_preference": str(self.diet_preference),
            "target_calories": self.target_calories,
            "estimated_calories": self.estimated_calories,
            "water_target_ml": self.water_target_ml,
            "protein_g": self.protein_g,
            "carbohydrates_g": self.carbohydrates_g,
            "fat_g": self.fat_g,
            "meals": [meal.to_dict() for meal in self.meals],
        }
