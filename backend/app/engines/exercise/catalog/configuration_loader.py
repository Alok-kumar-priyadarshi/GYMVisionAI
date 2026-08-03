# file_name: configuration_loader.py

"""Loads and validates exercise configuration files.

Implements the Configuration Loader and Schema Validator components of
``docs/03_business/19_EXERCISE_ENGINE.md`` section 6.

The loader locates configuration files, parses them, validates them against
``ExerciseDefinition`` and reports precise errors. It performs no business logic:
searching, filtering and caching belong to the registry.

Per ``docs/01_foundation/10_CONFIGURATION_ARCHITECTURE.md`` principle CFG-005 an
invalid configuration prevents application startup, so every failure raises.
"""

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.engines.exercise.catalog.exercise_definition import ExerciseDefinition
from app.shared.exceptions import ExerciseConfigurationError

logger = logging.getLogger(__name__)

CONFIGURATION_SUFFIX = ".yaml"

EXERCISE_CONFIGURATION_DIRECTORY = (
    Path(__file__).resolve().parents[4] / "configuration" / "exercise"
)
"""Default location of the exercise configuration files."""


class ConfigurationLoader:
    """Reads exercise configuration files from a directory."""

    def __init__(self, configuration_directory: Path | None = None) -> None:
        """Create a loader.

        Args:
            configuration_directory: Directory holding the exercise configuration
                files. Defaults to the project's configuration directory.
        """
        self.configuration_directory = (
            configuration_directory or EXERCISE_CONFIGURATION_DIRECTORY
        )

    def load(self) -> tuple[ExerciseDefinition, ...]:
        """Load and validate every exercise configuration file.

        Returns:
            Validated definitions, ordered by exercise identifier.

        Raises:
            ExerciseConfigurationError: If the directory is missing or empty, a
                file cannot be parsed, a file fails schema validation, or an
                identifier or slug is duplicated.
        """
        paths = self._discover()
        definitions = [self._load_file(path) for path in paths]

        self._reject_duplicates(definitions, paths)

        logger.info("Loaded %d exercise configurations.", len(definitions))
        return tuple(sorted(definitions, key=lambda definition: definition.id))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _discover(self) -> list[Path]:
        """Return every configuration file in the directory, sorted by name."""
        directory = self.configuration_directory

        if not directory.is_dir():
            raise ExerciseConfigurationError(
                f"Exercise configuration directory not found: {directory}"
            )

        paths = sorted(directory.glob(f"*{CONFIGURATION_SUFFIX}"))
        if not paths:
            raise ExerciseConfigurationError(
                f"No exercise configuration files found in {directory}"
            )
        return paths

    def _load_file(self, path: Path) -> ExerciseDefinition:
        """Parse and validate a single configuration file."""
        raw_configuration = self._parse(path)

        try:
            return ExerciseDefinition(**raw_configuration)
        except ValidationError as error:
            logger.error("Exercise configuration validation failed: %s", path.name)
            raise ExerciseConfigurationError(
                self._format_validation_error(path, error)
            ) from error

    @staticmethod
    def _parse(path: Path) -> dict:
        """Read one YAML file and confirm it describes a single exercise."""
        try:
            content = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise ExerciseConfigurationError(
                f"{path.name}: file is not valid YAML."
            ) from error
        except OSError as error:
            raise ExerciseConfigurationError(
                f"{path.name}: file could not be read."
            ) from error

        if not isinstance(content, dict):
            raise ExerciseConfigurationError(
                f"{path.name}: expected a mapping of exercise fields, "
                f"received {type(content).__name__}."
            )
        return content

    @staticmethod
    def _format_validation_error(path: Path, error: ValidationError) -> str:
        """Render a validation failure as file, field, expectation and input.

        The format follows ``10_CONFIGURATION_ARCHITECTURE.md`` section 17, which
        requires every error to identify the file, the field, what was expected
        and what was received.
        """
        problems = []
        for issue in error.errors():
            field = ".".join(str(part) for part in issue["loc"]) or "<root>"
            problems.append(
                f"field '{field}': {issue['msg']} (received {issue['input']!r})"
            )
        return f"{path.name}: " + "; ".join(problems)

    @staticmethod
    def _reject_duplicates(
        definitions: list[ExerciseDefinition], paths: list[Path]
    ) -> None:
        """Ensure identifiers and slugs are unique across the library."""
        for attribute in ("id", "slug"):
            seen: dict[str, str] = {}
            for definition, path in zip(definitions, paths):
                value = getattr(definition, attribute)
                if value in seen:
                    logger.error("Duplicate exercise %s detected: %s", attribute, value)
                    raise ExerciseConfigurationError(
                        f"Duplicate exercise {attribute} '{value}' in "
                        f"{seen[value]} and {path.name}."
                    )
                seen[value] = path.name
