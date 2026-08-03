# file_name: test_detectors.py

"""Behavioural tests for the exercise detectors.

These tests cover documented detector behaviour only: stage transitions,
repetition counting, visibility gating and the shape of the normalised result.
Threshold values themselves belong to the individual detectors and are treated
as given.
"""

import pytest

from app.engines.exercise.detector_registry import (
    DETECTORS,
    HOLD_BASED_EXERCISES,
    DetectorRegistry,
)
from app.engines.exercise.detector_result import DetectorResult
from tests.fixtures.landmarks import (
    LEFT_ANKLE,
    LEFT_HIP,
    LEFT_SHOULDER,
    build_pose,
    push_up_pose,
    squat_pose,
)

ALL_EXERCISES = sorted(DETECTORS)


# ---------------------------------------------------------------------------
# Contract compliance across every supported exercise
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("exercise_id", ALL_EXERCISES)
def test_every_detector_returns_the_documented_contract(exercise_id):
    detector = DetectorRegistry.create(exercise_id)

    result = detector.analyze(build_pose())

    assert isinstance(result, DetectorResult)
    assert result.exercise == exercise_id
    assert isinstance(result.reps, int)
    assert result.reps >= 0
    assert result.stage is None or isinstance(result.stage, str)
    assert isinstance(result.feedback, tuple)
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.parametrize("exercise_id", ALL_EXERCISES)
def test_every_detector_tolerates_an_untracked_skeleton(exercise_id):
    detector = DetectorRegistry.create(exercise_id)

    result = detector.analyze(build_pose(visibility=0.1))

    assert result.reps == 0
    assert result.confidence == pytest.approx(0.1)


@pytest.mark.parametrize("exercise_id", ALL_EXERCISES)
def test_every_detector_is_stable_across_repeated_frames(exercise_id):
    detector = DetectorRegistry.create(exercise_id)
    pose = build_pose()

    first = detector.analyze(pose)
    second = detector.analyze(pose)

    assert second.reps >= first.reps


@pytest.mark.parametrize("exercise_id", ALL_EXERCISES)
def test_reset_returns_a_detector_to_its_initial_state(exercise_id):
    detector = DetectorRegistry.create(exercise_id)
    detector.analyze(build_pose())
    detector.reps = 9

    detector.reset()

    assert detector.reps == 0


# ---------------------------------------------------------------------------
# Repetition counting
# ---------------------------------------------------------------------------


def test_push_ups_count_one_repetition_per_descent():
    detector = DetectorRegistry.create("push_ups")

    detector.analyze(push_up_pose(180))
    assert detector.analyze(push_up_pose(180)).stage == "up"

    result = detector.analyze(push_up_pose(60))

    assert result.stage == "down"
    assert result.reps == 1


def test_push_ups_count_repeated_cycles():
    detector = DetectorRegistry.create("push_ups")

    for _ in range(3):
        detector.analyze(push_up_pose(180))
        detector.analyze(push_up_pose(60))

    assert detector.analyze(push_up_pose(180)).reps == 3


def test_push_ups_ignore_a_descent_without_a_preceding_extension():
    detector = DetectorRegistry.create("push_ups")

    result = detector.analyze(push_up_pose(60))

    assert result.reps == 0


def test_push_ups_expose_the_elbow_angle_as_a_metric():
    detector = DetectorRegistry.create("push_ups")

    result = detector.analyze(push_up_pose(180))

    assert result.metrics["elbow_angle"] == pytest.approx(180, abs=1)


def test_push_ups_do_not_count_while_the_skeleton_is_untracked():
    detector = DetectorRegistry.create("push_ups")

    detector.analyze(push_up_pose(180, visibility=0.4))
    result = detector.analyze(push_up_pose(60, visibility=0.4))

    assert result.reps == 0
    assert result.stage is None


def test_bodyweight_squats_count_one_repetition_per_descent():
    detector = DetectorRegistry.create("bodyweight_squats")

    detector.analyze(squat_pose(180))
    result = detector.analyze(squat_pose(60))

    assert result.stage == "down"
    assert result.reps == 1


def test_bodyweight_squats_report_form_feedback():
    detector = DetectorRegistry.create("bodyweight_squats")

    result = detector.analyze(squat_pose(180))

    assert result.metrics["form_status"] == "GOOD FORM"
    assert result.feedback == ("Good form",)


# ---------------------------------------------------------------------------
# Hold-based exercises
# ---------------------------------------------------------------------------


def test_plank_reports_a_holding_stage_when_the_body_is_aligned():
    detector = DetectorRegistry.create("plank")
    aligned = build_pose(
        {LEFT_SHOULDER: (0.30, 0.50), LEFT_HIP: (0.50, 0.50), LEFT_ANKLE: (0.70, 0.50)}
    )

    assert detector.analyze(aligned).stage == "holding"


def test_plank_asks_for_a_correction_when_the_hips_drop():
    detector = DetectorRegistry.create("plank")
    sagging = build_pose(
        {LEFT_SHOULDER: (0.30, 0.50), LEFT_HIP: (0.50, 0.65), LEFT_ANKLE: (0.70, 0.50)}
    )

    assert detector.analyze(sagging).stage == "adjust_form"


def test_wall_sit_confirms_a_correct_hold():
    detector = DetectorRegistry.create("wall_sit")

    result = detector.analyze(squat_pose(90))

    assert result.stage == "holding"
    assert result.feedback == ("Good hold",)


def test_wall_sit_asks_for_a_correction_outside_the_target_angle():
    detector = DetectorRegistry.create("wall_sit")

    result = detector.analyze(squat_pose(180))

    assert result.stage == "adjust"
    assert result.feedback == ("Adjust knee angle to 90 deg",)


@pytest.mark.parametrize("exercise_id", sorted(HOLD_BASED_EXERCISES))
def test_hold_based_detectors_do_not_measure_hold_time(exercise_id):
    # Detectors receive no timing information, so hold duration is accumulated by
    # the exercise session service rather than by the detector.
    detector = DetectorRegistry.create(exercise_id)

    result = detector.analyze(build_pose())

    assert "hold_time" not in result.metrics
