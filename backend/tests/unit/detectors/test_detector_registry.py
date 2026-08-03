# file_name: test_detector_registry.py

"""Unit tests for the detector registry.

The registry is the single place that decides which exercises the product
supports, so these tests pin it against
``docs/12_reference/01_SUPPORTED_EXERCISES.md``.
"""

import pytest

from app.engines.exercise.base_exercise import BaseExercise
from app.engines.exercise.detector_registry import (
    DETECTORS,
    HOLD_BASED_EXERCISES,
    DetectorRegistry,
)
from app.shared.exceptions import DetectorUnavailableError, UnsupportedExerciseError

SUPPORTED_EXERCISE_COUNT = 29

EXPECTED_EXERCISES = {
    # Warm-up
    "jumping_jacks",
    "high_knees",
    "butt_kicks",
    "hip_circles",
    # Lower Body
    "bodyweight_squats",
    "sumo_squats",
    "reverse_lunges",
    "forward_lunges",
    "side_lunges",
    "glute_bridges",
    "single_leg_glute_bridges",
    "wall_sit",
    "calf_raises",
    "step_ups",
    # Upper Body
    "push_ups",
    "knee_push_ups",
    "incline_push_ups",
    "pike_push_ups",
    "triceps_dips",
    # Core
    "plank",
    "side_plank",
    "bicycle_crunches",
    "mountain_climbers",
    "dead_bug",
    "bird_dog",
    "leg_raises",
    "russian_twists",
    "flutter_kicks",
    # Full Body
    "burpees",
}


def test_registry_matches_the_supported_exercise_reference():
    assert set(DETECTORS) == EXPECTED_EXERCISES


def test_registry_registers_every_supported_exercise():
    assert len(DETECTORS) == SUPPORTED_EXERCISE_COUNT


def test_arm_circles_is_not_supported():
    # An implementation exists but the exercise is not part of Version 1.
    assert DetectorRegistry.is_supported("arm_circles") is False


def test_every_registered_detector_derives_from_the_base_class():
    for exercise_id, detector_class in DETECTORS.items():
        assert issubclass(detector_class, BaseExercise), exercise_id


def test_every_exercise_has_a_distinct_detector():
    assert len(set(DETECTORS.values())) == len(DETECTORS)


@pytest.mark.parametrize("exercise_id", sorted(EXPECTED_EXERCISES))
def test_detector_identity_matches_its_registry_key(exercise_id):
    assert DetectorRegistry.create(exercise_id).exercise_id == exercise_id


@pytest.mark.parametrize("exercise_id", sorted(EXPECTED_EXERCISES))
def test_created_detectors_start_from_a_clean_state(exercise_id):
    detector = DetectorRegistry.create(exercise_id)

    assert detector.reps == 0
    assert detector.stage in (None, "active", "standing", "down")


def test_create_returns_an_independent_instance_per_session():
    first = DetectorRegistry.create("push_ups")
    second = DetectorRegistry.create("push_ups")

    first.reps = 5

    assert first is not second
    assert second.reps == 0


def test_is_supported_recognises_registered_exercises():
    assert DetectorRegistry.is_supported("push_ups") is True
    assert DetectorRegistry.is_supported("bench_press") is False


def test_supported_exercises_lists_every_registered_identifier():
    assert set(DetectorRegistry.supported_exercises()) == EXPECTED_EXERCISES


def test_detector_class_returns_the_registered_class():
    assert DetectorRegistry.detector_class("plank") is DETECTORS["plank"]


def test_unknown_exercise_raises_the_documented_error():
    with pytest.raises(UnsupportedExerciseError) as error:
        DetectorRegistry.create("bench_press")

    assert error.value.error_code == "EXERCISE-005"
    assert error.value.http_status == 400
    assert "bench_press" in error.value.message


def test_detector_class_rejects_unknown_exercises():
    with pytest.raises(UnsupportedExerciseError):
        DetectorRegistry.detector_class("bench_press")


def test_failing_detector_reports_the_detector_as_unavailable(monkeypatch):
    class BrokenDetector(BaseExercise):
        def reset(self) -> None:
            raise RuntimeError("detector could not initialise")

        def process(self, landmarks):
            return {}

    monkeypatch.setitem(DETECTORS, "push_ups", BrokenDetector)

    with pytest.raises(DetectorUnavailableError) as error:
        DetectorRegistry.create("push_ups")

    assert error.value.error_code == "EXERCISE-006"
    assert error.value.http_status == 503


def test_hold_based_exercises_are_all_registered():
    assert HOLD_BASED_EXERCISES <= set(DETECTORS)


def test_hold_based_exercises_match_the_reference():
    assert HOLD_BASED_EXERCISES == {"plank", "side_plank", "wall_sit"}
