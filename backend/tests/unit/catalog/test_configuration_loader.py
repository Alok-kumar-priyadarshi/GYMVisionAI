# file_name: test_configuration_loader.py

"""Unit tests for the exercise configuration loader."""

from pathlib import Path

import pytest
import yaml

from app.engines.exercise.catalog.configuration_loader import ConfigurationLoader
from app.shared.exceptions import ExerciseConfigurationError

BASE_CONFIGURATION = {
    "id": "EX-0015",
    "version": "1.0.0",
    "slug": "push_ups",
    "name": "Push-ups",
    "category": "Upper Body",
    "difficulty": "Intermediate",
    "exercise_type": "Repetition",
    "movement_type": "Compound",
    "equipment": ["none"],
    "primary_muscles": ["Chest"],
    "secondary_muscles": ["Core"],
    "instructions": ["Start in a high plank.", "Lower your chest."],
}


def write_configuration(directory: Path, filename: str, **overrides) -> Path:
    """Write one exercise configuration file and return its path."""
    configuration = {**BASE_CONFIGURATION, **overrides}
    path = directory / filename
    path.write_text(yaml.safe_dump(configuration), encoding="utf-8")
    return path


def test_loads_every_configuration_file(tmp_path):
    write_configuration(tmp_path, "push_ups.yaml")
    write_configuration(tmp_path, "plank.yaml", id="EX-0020", slug="plank", name="Plank")

    definitions = ConfigurationLoader(tmp_path).load()

    assert len(definitions) == 2
    assert {definition.slug for definition in definitions} == {"push_ups", "plank"}


def test_definitions_are_ordered_by_identifier(tmp_path):
    write_configuration(tmp_path, "z.yaml", id="EX-0020", slug="plank")
    write_configuration(tmp_path, "a.yaml", id="EX-0001", slug="jumping_jacks")

    definitions = ConfigurationLoader(tmp_path).load()

    assert [definition.id for definition in definitions] == ["EX-0001", "EX-0020"]


def test_non_configuration_files_are_ignored(tmp_path):
    write_configuration(tmp_path, "push_ups.yaml")
    (tmp_path / "notes.md").write_text("not a configuration file", encoding="utf-8")

    assert len(ConfigurationLoader(tmp_path).load()) == 1


def test_missing_directory_is_rejected(tmp_path):
    with pytest.raises(ExerciseConfigurationError) as error:
        ConfigurationLoader(tmp_path / "absent").load()

    assert "not found" in str(error.value)


def test_empty_directory_is_rejected(tmp_path):
    with pytest.raises(ExerciseConfigurationError) as error:
        ConfigurationLoader(tmp_path).load()

    assert "No exercise configuration files" in str(error.value)


def test_malformed_yaml_is_rejected(tmp_path):
    (tmp_path / "push_ups.yaml").write_text("id: [unclosed", encoding="utf-8")

    with pytest.raises(ExerciseConfigurationError) as error:
        ConfigurationLoader(tmp_path).load()

    assert "push_ups.yaml" in str(error.value)


def test_a_configuration_that_is_not_a_mapping_is_rejected(tmp_path):
    (tmp_path / "push_ups.yaml").write_text("- one\n- two\n", encoding="utf-8")

    with pytest.raises(ExerciseConfigurationError) as error:
        ConfigurationLoader(tmp_path).load()

    assert "expected a mapping" in str(error.value)


def test_schema_violations_identify_the_file_and_field(tmp_path):
    write_configuration(tmp_path, "push_ups.yaml", exercise_type="Reps")

    with pytest.raises(ExerciseConfigurationError) as error:
        ConfigurationLoader(tmp_path).load()

    message = str(error.value)
    assert "push_ups.yaml" in message
    assert "exercise_type" in message
    assert "Reps" in message


def test_missing_required_field_is_reported(tmp_path):
    configuration = dict(BASE_CONFIGURATION)
    del configuration["category"]
    (tmp_path / "push_ups.yaml").write_text(
        yaml.safe_dump(configuration), encoding="utf-8"
    )

    with pytest.raises(ExerciseConfigurationError) as error:
        ConfigurationLoader(tmp_path).load()

    assert "category" in str(error.value)


def test_duplicate_identifiers_are_rejected(tmp_path):
    write_configuration(tmp_path, "a.yaml", slug="push_ups")
    write_configuration(tmp_path, "b.yaml", slug="knee_push_ups")

    with pytest.raises(ExerciseConfigurationError) as error:
        ConfigurationLoader(tmp_path).load()

    assert "Duplicate exercise id" in str(error.value)


def test_duplicate_slugs_are_rejected(tmp_path):
    write_configuration(tmp_path, "a.yaml", id="EX-0015")
    write_configuration(tmp_path, "b.yaml", id="EX-0016")

    with pytest.raises(ExerciseConfigurationError) as error:
        ConfigurationLoader(tmp_path).load()

    assert "Duplicate exercise slug" in str(error.value)


def test_configuration_error_carries_the_documented_error_code():
    error = ExerciseConfigurationError()

    assert error.error_code == "SYSTEM-001"
    assert error.http_status == 500
