# file_name: test_template_loader.py

"""Unit tests for the workout template loader."""

from pathlib import Path

import pytest
import yaml

from app.engines.workout.template_loader import TemplateLoader
from app.engines.workout.workout_profile import FitnessGoal
from app.shared.exceptions import WorkoutConfigurationError
from tests.fixtures.workout import TEMPLATE_DEFAULTS


def write_template(directory: Path, filename: str, **overrides) -> Path:
    """Write one workout template file and return its path."""
    payload = {**TEMPLATE_DEFAULTS, **overrides}
    path = directory / filename
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def write_every_goal(directory: Path) -> None:
    """Write a valid template for each supported goal."""
    for index, goal in enumerate(FitnessGoal, start=1):
        write_template(
            directory,
            f"{index}.yaml",
            id=f"WO-{index:04d}",
            goal=str(goal),
            name=str(goal),
        )


def test_loads_a_template_for_every_goal(tmp_path):
    write_every_goal(tmp_path)

    templates = TemplateLoader(tmp_path).load()

    assert set(templates) == set(FitnessGoal)


def test_templates_are_keyed_by_goal(tmp_path):
    write_every_goal(tmp_path)

    templates = TemplateLoader(tmp_path).load()

    assert templates[FitnessGoal.WEIGHT_LOSS].goal is FitnessGoal.WEIGHT_LOSS


def test_the_result_cannot_be_modified(tmp_path):
    write_every_goal(tmp_path)

    templates = TemplateLoader(tmp_path).load()

    with pytest.raises(TypeError):
        templates[FitnessGoal.WEIGHT_LOSS] = None


def test_missing_directory_is_rejected(tmp_path):
    with pytest.raises(WorkoutConfigurationError) as error:
        TemplateLoader(tmp_path / "absent").load()

    assert "not found" in str(error.value)


def test_empty_directory_is_rejected(tmp_path):
    with pytest.raises(WorkoutConfigurationError) as error:
        TemplateLoader(tmp_path).load()

    assert "No workout template files" in str(error.value)


def test_malformed_yaml_is_rejected(tmp_path):
    (tmp_path / "broken.yaml").write_text("id: [unclosed", encoding="utf-8")

    with pytest.raises(WorkoutConfigurationError) as error:
        TemplateLoader(tmp_path).load()

    assert "broken.yaml" in str(error.value)


def test_a_template_that_is_not_a_mapping_is_rejected(tmp_path):
    (tmp_path / "list.yaml").write_text("- one\n- two\n", encoding="utf-8")

    with pytest.raises(WorkoutConfigurationError) as error:
        TemplateLoader(tmp_path).load()

    assert "expected a mapping" in str(error.value)


def test_schema_violations_identify_the_file_and_field(tmp_path):
    write_template(tmp_path, "bad.yaml", seconds_per_repetition=0)

    with pytest.raises(WorkoutConfigurationError) as error:
        TemplateLoader(tmp_path).load()

    message = str(error.value)
    assert "bad.yaml" in message
    assert "seconds_per_repetition" in message


def test_duplicate_goals_are_rejected(tmp_path):
    write_template(tmp_path, "a.yaml", id="WO-0001")
    write_template(tmp_path, "b.yaml", id="WO-0002")

    with pytest.raises(WorkoutConfigurationError) as error:
        TemplateLoader(tmp_path).load()

    assert "Duplicate workout template" in str(error.value)


def test_a_template_missing_a_fitness_level_is_rejected(tmp_path):
    write_template(tmp_path, "partial.yaml", levels=[TEMPLATE_DEFAULTS["levels"][0]])

    with pytest.raises(WorkoutConfigurationError) as error:
        TemplateLoader(tmp_path).load()

    assert "every fitness level" in str(error.value)


def test_a_goal_without_a_template_is_rejected(tmp_path):
    write_template(tmp_path, "only_one.yaml")

    with pytest.raises(WorkoutConfigurationError) as error:
        TemplateLoader(tmp_path).load()

    assert "No workout template for goal" in str(error.value)


def test_configuration_error_carries_the_documented_error_code():
    error = WorkoutConfigurationError()

    assert error.error_code == "SYSTEM-001"
    assert error.http_status == 500
