# file_name: food_loader.py

"""Loads and validates food and meal template configuration.

Implements the Configuration Loader and Schema Validator components of
``docs/03_business/24_FOOD_CATALOG_ENGINE.md`` section 6.

Section 14 requires invalid configuration to prevent startup, so every failure
raises rather than being skipped.
"""

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.engines.nutrition.food_definition import FoodDefinition
from app.engines.nutrition.meal_template import MealTemplate
from app.shared.exceptions import NutritionConfigurationError

logger = logging.getLogger(__name__)

CONFIGURATION_SUFFIX = ".yaml"

NUTRITION_CONFIGURATION_DIRECTORY = (
    Path(__file__).resolve().parents[3] / "configuration" / "nutrition"
)
"""Default root of the nutrition configuration."""

FOODS_DIRECTORY_NAME = "foods"
MEAL_TEMPLATES_DIRECTORY_NAME = "meal_templates"


class FoodLoader:
    """Reads the food catalogue and its meal templates from disk."""

    def __init__(self, configuration_directory: Path | None = None) -> None:
        """Create a loader.

        Args:
            configuration_directory: Root directory holding ``foods`` and
                ``meal_templates``. Defaults to the project's configuration.
        """
        self.configuration_directory = (
            configuration_directory or NUTRITION_CONFIGURATION_DIRECTORY
        )

    def load_foods(self) -> tuple[FoodDefinition, ...]:
        """Load and validate every food.

        Returns:
            Validated foods, ordered by identifier.

        Raises:
            NutritionConfigurationError: If a file is missing or invalid, or an
                identifier or name is duplicated.
        """
        paths = self._discover(FOODS_DIRECTORY_NAME)
        foods = [self._load(path, FoodDefinition) for path in paths]

        self._reject_duplicates(foods, paths, "id")
        self._reject_duplicates(foods, paths, "name")
        self._reject_duplicates(foods, paths, "slug")

        logger.info("Loaded %d foods.", len(foods))
        return tuple(sorted(foods, key=lambda food: food.id))

    def load_meal_templates(self) -> tuple[MealTemplate, ...]:
        """Load and validate every meal template.

        Returns:
            Validated templates, ordered by identifier.

        Raises:
            NutritionConfigurationError: If a file is missing or invalid, or an
                identifier is duplicated.
        """
        paths = self._discover(MEAL_TEMPLATES_DIRECTORY_NAME)
        templates = [self._load(path, MealTemplate) for path in paths]

        self._reject_duplicates(templates, paths, "id")

        logger.info("Loaded %d meal templates.", len(templates))
        return tuple(sorted(templates, key=lambda template: template.id))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _discover(self, subdirectory: str) -> list[Path]:
        """Return every configuration file in a subdirectory, sorted by name."""
        directory = self.configuration_directory / subdirectory

        if not directory.is_dir():
            raise NutritionConfigurationError(
                f"Nutrition configuration directory not found: {directory}"
            )

        paths = sorted(directory.glob(f"*{CONFIGURATION_SUFFIX}"))
        if not paths:
            raise NutritionConfigurationError(
                f"No configuration files found in {directory}"
            )
        return paths

    @staticmethod
    def _load(path: Path, schema: type) -> object:
        """Parse and validate a single configuration file."""
        try:
            content = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise NutritionConfigurationError(
                f"{path.name}: file is not valid YAML."
            ) from error
        except OSError as error:
            raise NutritionConfigurationError(
                f"{path.name}: file could not be read."
            ) from error

        if not isinstance(content, dict):
            raise NutritionConfigurationError(
                f"{path.name}: expected a mapping of fields, "
                f"received {type(content).__name__}."
            )

        try:
            return schema(**content)
        except ValidationError as error:
            logger.error("Nutrition configuration validation failed: %s", path.name)
            problems = []
            for issue in error.errors():
                field = ".".join(str(part) for part in issue["loc"]) or "<root>"
                problems.append(
                    f"field '{field}': {issue['msg']} (received {issue['input']!r})"
                )
            raise NutritionConfigurationError(
                f"{path.name}: " + "; ".join(problems)
            ) from error

    @staticmethod
    def _reject_duplicates(items: list, paths: list[Path], attribute: str) -> None:
        """Ensure an attribute is unique across the catalogue."""
        seen: dict[str, str] = {}
        for item, path in zip(items, paths):
            value = getattr(item, attribute)
            if value in seen:
                logger.error("Duplicate %s detected: %s", attribute, value)
                raise NutritionConfigurationError(
                    f"Duplicate {attribute} '{value}' in {seen[value]} and {path.name}."
                )
            seen[value] = path.name
