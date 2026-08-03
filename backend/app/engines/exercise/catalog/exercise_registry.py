# file_name: exercise_registry.py

"""In-memory registry of every supported exercise.

Implements the Registry, Cache Manager, Search Service and Filter Service
components of ``docs/03_business/19_EXERCISE_ENGINE.md``.

The registry is built once during startup and is read-only afterwards. Lookups
are dictionary based and therefore constant time, meeting the runtime lookup
target in section 16.

The Exercise Engine never performs pose estimation or repetition counting. It
only publishes validated exercise definitions.
"""

import logging
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from app.engines.exercise.catalog.configuration_loader import ConfigurationLoader
from app.engines.exercise.catalog.exercise_definition import (
    Difficulty,
    Equipment,
    ExerciseCategory,
    ExerciseDefinition,
    ExerciseType,
)
from app.engines.exercise.detector_registry import DetectorRegistry
from app.shared.exceptions import ExerciseConfigurationError, ExerciseNotFoundError

logger = logging.getLogger(__name__)


class ExerciseRegistry:
    """Read-only catalogue of validated exercise definitions."""

    def __init__(self, definitions: tuple[ExerciseDefinition, ...]) -> None:
        """Build the registry and its lookup indexes.

        Args:
            definitions: Validated exercise definitions.
        """
        self._definitions: tuple[ExerciseDefinition, ...] = tuple(definitions)
        self._by_slug: Mapping[str, ExerciseDefinition] = MappingProxyType(
            {definition.slug: definition for definition in self._definitions}
        )
        self._by_id: Mapping[str, ExerciseDefinition] = MappingProxyType(
            {definition.id: definition for definition in self._definitions}
        )
        logger.info("Exercise registry initialised with %d exercises.", len(self))

    def __len__(self) -> int:
        return len(self._definitions)

    def __contains__(self, slug: str) -> bool:
        return slug in self._by_slug

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def all(self) -> tuple[ExerciseDefinition, ...]:
        """Return every exercise, ordered by identifier."""
        return self._definitions

    def slugs(self) -> tuple[str, ...]:
        """Return every exercise slug."""
        return tuple(self._by_slug)

    def get(self, slug: str) -> ExerciseDefinition:
        """Return one exercise by slug.

        Args:
            slug: Stable exercise identifier such as ``push_ups``.

        Returns:
            The matching definition.

        Raises:
            ExerciseNotFoundError: If no exercise has that slug.
        """
        try:
            return self._by_slug[slug]
        except KeyError as error:
            raise ExerciseNotFoundError(f"Exercise '{slug}' not found.") from error

    def get_by_id(self, exercise_id: str) -> ExerciseDefinition:
        """Return one exercise by configuration identifier such as ``EX-0001``.

        Raises:
            ExerciseNotFoundError: If no exercise has that identifier.
        """
        try:
            return self._by_id[exercise_id]
        except KeyError as error:
            raise ExerciseNotFoundError(
                f"Exercise '{exercise_id}' not found."
            ) from error

    @staticmethod
    def detector_available(slug: str) -> bool:
        """Report whether a detector implementation is registered for a slug."""
        return DetectorRegistry.is_supported(slug)

    # ------------------------------------------------------------------
    # Search and filter
    # ------------------------------------------------------------------

    def search(self, query: str) -> tuple[ExerciseDefinition, ...]:
        """Return exercises matching a free-text query.

        Searches the fields listed in ``19_EXERCISE_ENGINE.md`` section 12:
        name, category, difficulty, target muscle, equipment and identifier.

        Args:
            query: Case-insensitive search term. A blank query matches nothing.

        Returns:
            Matching definitions in registry order.
        """
        term = query.strip().lower()
        if not term:
            return ()

        return tuple(
            definition
            for definition in self._definitions
            if term in self._searchable_text(definition)
        )

    def filter(
        self,
        *,
        category: ExerciseCategory | None = None,
        difficulty: Difficulty | None = None,
        exercise_type: ExerciseType | None = None,
        equipment_free: bool | None = None,
    ) -> tuple[ExerciseDefinition, ...]:
        """Return exercises matching every supplied filter.

        Filters combine with AND. Omitted filters are ignored.

        Args:
            category: Restrict to one exercise category.
            difficulty: Restrict to one difficulty level.
            exercise_type: Restrict to repetition or duration exercises.
            equipment_free: When ``True``, return only exercises that need no
                equipment beyond an optional mat.

        Returns:
            Matching definitions in registry order.
        """
        results = self._definitions

        if category is not None:
            results = tuple(item for item in results if item.category == category)
        if difficulty is not None:
            results = tuple(item for item in results if item.difficulty == difficulty)
        if exercise_type is not None:
            results = tuple(
                item for item in results if item.exercise_type == exercise_type
            )
        if equipment_free is not None:
            results = tuple(
                item for item in results if item.requires_equipment != equipment_free
            )
        return results

    @staticmethod
    def _searchable_text(definition: ExerciseDefinition) -> str:
        """Return the lower-cased text a search query is matched against."""
        parts = (
            definition.id,
            definition.slug,
            definition.name,
            definition.category,
            definition.difficulty,
            definition.exercise_type,
            *definition.muscles,
            *definition.equipment,
        )
        return " ".join(parts).lower()


def build_exercise_registry(
    configuration_directory: Path | None = None,
) -> ExerciseRegistry:
    """Load configuration and build a registry, verifying detector coverage.

    Args:
        configuration_directory: Directory holding the exercise configuration
            files. Defaults to the project's configuration directory.

    Returns:
        A registry containing every configured exercise.

    Raises:
        ExerciseConfigurationError: If configuration is invalid, or if the
            configured library and the detector registry disagree.
    """
    definitions = ConfigurationLoader(configuration_directory).load()
    registry = ExerciseRegistry(definitions)
    _verify_detector_coverage(registry)
    return registry


@lru_cache(maxsize=1)
def load_exercise_registry() -> ExerciseRegistry:
    """Return the application's exercise registry, building it on first use.

    Configuration is parsed exactly once. Every later call returns the cached
    registry, so no file system access occurs during request processing.
    """
    return build_exercise_registry()


def _verify_detector_coverage(registry: ExerciseRegistry) -> None:
    """Fail startup when the exercise library and detector registry disagree.

    ``contracts/exercises/04_GET_EXERCISES.md`` section 12 requires the API to
    return only implemented exercises, so a configured exercise without a
    detector, or a registered detector without configuration, is a startup error
    rather than something to discover at runtime.
    """
    configured = set(registry.slugs())
    implemented = set(DetectorRegistry.supported_exercises())

    missing_detectors = sorted(configured - implemented)
    if missing_detectors:
        raise ExerciseConfigurationError(
            "Configured exercises have no detector: " + ", ".join(missing_detectors)
        )

    missing_configuration = sorted(implemented - configured)
    if missing_configuration:
        raise ExerciseConfigurationError(
            "Registered detectors have no configuration: "
            + ", ".join(missing_configuration)
        )
