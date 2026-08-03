# file_name: template_loader.py

"""Loads and validates workout generation templates.

Mirrors the exercise configuration loader: it locates template files, parses
them, validates them and reports precise errors. An invalid template prevents
startup, per ``10_CONFIGURATION_ARCHITECTURE.md`` principle CFG-005.
"""

import logging
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml
from pydantic import ValidationError

from app.engines.workout.workout_profile import FitnessGoal
from app.engines.workout.workout_template import WorkoutTemplate
from app.shared.exceptions import WorkoutConfigurationError

logger = logging.getLogger(__name__)

CONFIGURATION_SUFFIX = ".yaml"

WORKOUT_CONFIGURATION_DIRECTORY = (
    Path(__file__).resolve().parents[3] / "configuration" / "workouts"
)
"""Default location of the workout template files."""


class TemplateLoader:
    """Reads workout template files from a directory."""

    def __init__(self, configuration_directory: Path | None = None) -> None:
        """Create a loader.

        Args:
            configuration_directory: Directory holding the workout templates.
                Defaults to the project's configuration directory.
        """
        self.configuration_directory = (
            configuration_directory or WORKOUT_CONFIGURATION_DIRECTORY
        )

    def load(self) -> Mapping[FitnessGoal, WorkoutTemplate]:
        """Load and validate every workout template.

        Returns:
            A read-only mapping of goal to template.

        Raises:
            WorkoutConfigurationError: If the directory is missing or empty, a
                file is invalid, a goal is described twice, or a supported goal
                or fitness level has no template.
        """
        templates: dict[FitnessGoal, WorkoutTemplate] = {}

        for path in self._discover():
            template = self._load_file(path)

            if template.goal in templates:
                raise WorkoutConfigurationError(
                    f"Duplicate workout template for goal '{template.goal}'."
                )
            if not template.covers_every_level():
                raise WorkoutConfigurationError(
                    f"{path.name}: template does not describe every fitness level."
                )
            templates[template.goal] = template

        self._require_every_goal(templates)

        logger.info("Loaded %d workout templates.", len(templates))
        return MappingProxyType(templates)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _discover(self) -> list[Path]:
        """Return every template file in the directory, sorted by name."""
        directory = self.configuration_directory

        if not directory.is_dir():
            raise WorkoutConfigurationError(
                f"Workout configuration directory not found: {directory}"
            )

        paths = sorted(directory.glob(f"*{CONFIGURATION_SUFFIX}"))
        if not paths:
            raise WorkoutConfigurationError(
                f"No workout template files found in {directory}"
            )
        return paths

    def _load_file(self, path: Path) -> WorkoutTemplate:
        """Parse and validate a single template file."""
        try:
            content = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise WorkoutConfigurationError(
                f"{path.name}: file is not valid YAML."
            ) from error
        except OSError as error:
            raise WorkoutConfigurationError(
                f"{path.name}: file could not be read."
            ) from error

        if not isinstance(content, dict):
            raise WorkoutConfigurationError(
                f"{path.name}: expected a mapping of template fields, "
                f"received {type(content).__name__}."
            )

        try:
            return WorkoutTemplate(**content)
        except ValidationError as error:
            logger.error("Workout template validation failed: %s", path.name)
            raise WorkoutConfigurationError(
                self._format_validation_error(path, error)
            ) from error

    @staticmethod
    def _format_validation_error(path: Path, error: ValidationError) -> str:
        """Render a validation failure as file, field, expectation and input."""
        problems = []
        for issue in error.errors():
            field = ".".join(str(part) for part in issue["loc"]) or "<root>"
            problems.append(
                f"field '{field}': {issue['msg']} (received {issue['input']!r})"
            )
        return f"{path.name}: " + "; ".join(problems)

    @staticmethod
    def _require_every_goal(templates: Mapping[FitnessGoal, WorkoutTemplate]) -> None:
        """Ensure every supported goal has a template."""
        missing = sorted(str(goal) for goal in FitnessGoal if goal not in templates)
        if missing:
            raise WorkoutConfigurationError(
                "No workout template for goal: " + ", ".join(missing)
            )


@lru_cache(maxsize=1)
def load_workout_templates() -> Mapping[FitnessGoal, WorkoutTemplate]:
    """Return the application's workout templates, loading them on first use."""
    return TemplateLoader().load()
