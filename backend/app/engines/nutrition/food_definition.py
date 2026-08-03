# file_name: food_definition.py

"""Validated definition of one food item.

``FoodDefinition`` is an output contract of the Food Catalog Engine described in
``docs/03_business/24_FOOD_CATALOG_ENGINE.md`` sections 5 and 8, and the schema
every food configuration file is validated against.

Nutritional data is immutable at runtime, per section 20.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.value_objects.enums import (
    DietPreference,
    FoodCategory,
    MealType,
)

__all__ = [
    "DietPreference",
    "FOOD_ID_PATTERN",
    "FoodCategory",
    "FoodDefinition",
    "MealType",
    "SLUG_PATTERN",
    "VERSION_PATTERN",
]

FOOD_ID_PATTERN = r"^FD-\d{4}$"
SLUG_PATTERN = r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$"
VERSION_PATTERN = r"^\d+\.\d+\.\d+$"

CALORIES_PER_GRAM_PROTEIN = 4
CALORIES_PER_GRAM_CARBOHYDRATE = 4
CALORIES_PER_GRAM_FAT = 9

MACRONUTRIENT_TOLERANCE = 0.25
"""Relative slack allowed between stated and macronutrient-derived calories."""

MACRONUTRIENT_ABSOLUTE_TOLERANCE = 25.0
"""Absolute slack in kcal, so fibre-heavy low-calorie foods still validate."""


class FoodDefinition(BaseModel):
    """One food item, loaded from a configuration file.

    Attributes:
        id: Catalogue identifier such as ``FD-0001``.
        slug: Stable machine identifier.
        name: Display name, unique across the catalogue.
        category: Food grouping.
        calories: Energy per serving, in kcal.
        protein_g: Protein per serving, in grams.
        carbohydrates_g: Carbohydrate per serving, in grams.
        fat_g: Fat per serving, in grams.
        serving_size: Human-readable serving the values describe.
        meal_types: Meals the food is appropriate for.
        diet_tags: Dietary preferences the food is suitable for.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=FOOD_ID_PATTERN)
    version: str = Field(pattern=VERSION_PATTERN)
    slug: str = Field(pattern=SLUG_PATTERN)
    name: str = Field(min_length=1)
    category: FoodCategory
    calories: float = Field(gt=0)
    protein_g: float = Field(ge=0)
    carbohydrates_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    serving_size: str = Field(min_length=1)
    meal_types: tuple[MealType, ...] = Field(min_length=1)
    diet_tags: tuple[DietPreference, ...] = Field(min_length=1)

    @property
    def derived_calories(self) -> float:
        """Return the energy implied by the macronutrients, using Atwater factors."""
        return (
            self.protein_g * CALORIES_PER_GRAM_PROTEIN
            + self.carbohydrates_g * CALORIES_PER_GRAM_CARBOHYDRATE
            + self.fat_g * CALORIES_PER_GRAM_FAT
        )

    @model_validator(mode="after")
    def _macronutrients_match_calories(self) -> "FoodDefinition":
        """Reject nutrition values that contradict each other.

        Section 13 requires valid macronutrients and section 14 lists invalid
        nutrition values as a startup error. Fibre and sugar alcohols make an
        exact match impossible, so a generous tolerance is allowed.
        """
        allowed = max(
            self.calories * MACRONUTRIENT_TOLERANCE, MACRONUTRIENT_ABSOLUTE_TOLERANCE
        )
        if abs(self.derived_calories - self.calories) > allowed:
            raise ValueError(
                f"macronutrients imply {self.derived_calories:.0f} kcal but "
                f"{self.calories:.0f} kcal is declared"
            )
        return self

    def suits(self, preference: DietPreference) -> bool:
        """Report whether the food is allowed for a dietary preference."""
        return preference in self.diet_tags

    def served_at(self, meal_type: MealType) -> bool:
        """Report whether the food is appropriate for a meal."""
        return meal_type in self.meal_types
