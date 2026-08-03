# file_name: test_base_exercise.py

"""Unit tests for the shared detector base class and its output contract."""

import math

import pytest

from app.engines.exercise.base_exercise import POSE_LANDMARK_COUNT, BaseExercise
from app.engines.exercise.detector_result import DetectorResult
from app.shared.exceptions import InvalidLandmarksError
from tests.fixtures.landmarks import FakeLandmark, build_pose, limb_points


class StubDetector(BaseExercise):
    """Minimal detector used to exercise the base class in isolation."""

    raw_result: dict = {}
    reset_calls = 0

    def reset(self) -> None:
        self.reps = 0
        self.stage = None
        self.reset_calls = getattr(self, "reset_calls", 0) + 1

    def process(self, landmarks):
        return dict(self.raw_result)


class SingleLegGluteBridgesStubDetector(StubDetector):
    """Used only to verify identifier derivation for multi-word class names."""


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("expected_angle", [0.0, 30.0, 45.0, 90.0, 120.0, 180.0])
def test_calculate_angle_matches_constructed_angle(expected_angle):
    vertex = (0.5, 0.5)
    proximal, distal = limb_points(vertex, expected_angle)

    angle = BaseExercise.calculate_angle(proximal, vertex, distal)

    assert angle == pytest.approx(expected_angle, abs=1e-6)


def test_calculate_angle_is_order_independent():
    first, mid, last = (0.5, 0.2), (0.5, 0.5), (0.8, 0.5)

    assert BaseExercise.calculate_angle(first, mid, last) == pytest.approx(
        BaseExercise.calculate_angle(last, mid, first)
    )


def test_calculate_angle_never_exceeds_a_straight_angle():
    # A reflex configuration must be reported as its interior equivalent.
    angle = BaseExercise.calculate_angle((0.5, 0.3), (0.5, 0.5), (0.4, 0.3))

    assert 0.0 <= angle <= 180.0


def test_calculate_angle_with_coincident_points_does_not_raise():
    assert BaseExercise.calculate_angle((0.5, 0.5), (0.5, 0.5), (0.5, 0.5)) == 0.0


def test_calculate_distance():
    assert BaseExercise.calculate_distance((0.0, 0.0), (0.3, 0.4)) == pytest.approx(0.5)


def test_midpoint():
    assert BaseExercise.midpoint((0.2, 0.4), (0.6, 0.8)) == pytest.approx((0.4, 0.6))


def test_get_point_returns_landmark_coordinates():
    landmarks = build_pose({11: (0.42, 0.25)})

    assert BaseExercise.get_point(landmarks, 11) == pytest.approx((0.42, 0.25))


def test_is_visible_uses_the_detector_threshold():
    detector = StubDetector()
    landmarks = build_pose(visibility=1.0)
    landmarks[13].visibility = 0.5

    assert detector.is_visible(landmarks, 11, 12) is True
    assert detector.is_visible(landmarks, 11, 13) is False


# ---------------------------------------------------------------------------
# Landmark validation
# ---------------------------------------------------------------------------


def test_validate_landmarks_accepts_a_full_skeleton():
    BaseExercise.validate_landmarks(build_pose())


def test_validate_landmarks_rejects_none():
    with pytest.raises(InvalidLandmarksError):
        BaseExercise.validate_landmarks(None)


def test_validate_landmarks_rejects_an_incomplete_skeleton():
    with pytest.raises(InvalidLandmarksError) as error:
        BaseExercise.validate_landmarks(build_pose()[:10])

    assert str(POSE_LANDMARK_COUNT) in str(error.value)


def test_validate_landmarks_rejects_objects_without_coordinates():
    with pytest.raises(InvalidLandmarksError):
        BaseExercise.validate_landmarks([object()] * POSE_LANDMARK_COUNT)


def test_invalid_landmarks_error_carries_the_documented_error_code():
    error = InvalidLandmarksError()

    assert error.error_code == "VALIDATION-003"
    assert error.http_status == 422


# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------


def test_construction_resets_runtime_state():
    detector = StubDetector()

    assert detector.reps == 0
    assert detector.stage is None
    assert detector.reset_calls == 1


def test_exercise_id_is_derived_from_the_class_name():
    assert StubDetector().exercise_id == "stub"
    assert (
        SingleLegGluteBridgesStubDetector().exercise_id
        == "single_leg_glute_bridges_stub"
    )


def test_explicit_exercise_id_overrides_derivation():
    class OddlyNamed(StubDetector):
        EXERCISE_ID = "wall_sit"

    assert OddlyNamed().exercise_id == "wall_sit"


# ---------------------------------------------------------------------------
# Output normalisation
# ---------------------------------------------------------------------------


def test_analyze_normalises_raw_detector_output():
    detector = StubDetector()
    detector.raw_result = {
        "reps": 3,
        "stage": "up",
        "elbow_angle": 164,
        "form_status": "GOOD FORM",
    }

    result = detector.analyze(build_pose())

    assert isinstance(result, DetectorResult)
    assert result.exercise == "stub"
    assert result.reps == 3
    assert result.stage == "up"
    assert result.metrics == {"elbow_angle": 164, "form_status": "GOOD FORM"}
    assert result.feedback == ("Good form",)


def test_analyze_reports_every_status_field_as_feedback():
    detector = StubDetector()
    detector.raw_result = {
        "reps": 0,
        "stage": None,
        "form_status": "KNEES CAVING IN",
        "stance_status": "NARROW STANCE",
    }

    result = detector.analyze(build_pose())

    assert result.feedback == ("Knees caving in", "Narrow stance")


def test_analyze_produces_no_feedback_without_status_fields():
    detector = StubDetector()
    detector.raw_result = {"reps": 2, "stage": "down", "elbow_angle": 90}

    assert detector.analyze(build_pose()).feedback == ()


def test_analyze_truncates_partial_repetitions():
    # Alternating and rotational detectors accumulate fractional repetitions.
    detector = StubDetector()
    detector.raw_result = {"reps": 2.5, "stage": "active"}

    assert detector.analyze(build_pose()).reps == 2


def test_analyze_falls_back_to_runtime_state_when_reps_are_absent():
    detector = StubDetector()
    detector.reps = 7
    detector.raw_result = {"stage": "up"}

    assert detector.analyze(build_pose()).reps == 7


def test_analyze_reports_a_missing_stage_as_none():
    detector = StubDetector()
    detector.raw_result = {"reps": 0}

    assert detector.analyze(build_pose()).stage is None


def test_analyze_validates_the_frame_before_processing():
    detector = StubDetector()

    with pytest.raises(InvalidLandmarksError):
        detector.analyze(build_pose()[:5])


def test_confidence_is_the_mean_visibility_of_the_skeleton():
    detector = StubDetector()
    detector.raw_result = {"reps": 0, "stage": None}

    result = detector.analyze(build_pose(visibility=0.9))

    assert result.confidence == pytest.approx(0.9)


def test_confidence_uses_required_landmarks_when_declared():
    class ShoulderDetector(StubDetector):
        REQUIRED_LANDMARKS = (11, 12)

    detector = ShoulderDetector()
    detector.raw_result = {"reps": 0, "stage": None}
    landmarks = build_pose(visibility=1.0)
    landmarks[11].visibility = 0.5
    landmarks[12].visibility = 0.7

    assert detector.analyze(landmarks).confidence == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Contract immutability
# ---------------------------------------------------------------------------


def test_detector_result_is_frozen():
    result = DetectorResult("push_ups", 1, "up", {}, (), 1.0)

    with pytest.raises(Exception):
        result.reps = 2


def test_detector_result_metrics_cannot_be_mutated():
    result = DetectorResult("push_ups", 1, "up", {"elbow_angle": 90}, (), 1.0)

    with pytest.raises(TypeError):
        result.metrics["elbow_angle"] = 120


def test_detector_result_does_not_alias_the_caller_mapping():
    metrics = {"elbow_angle": 90}
    result = DetectorResult("push_ups", 1, "up", metrics, (), 1.0)

    metrics["elbow_angle"] = 120

    assert result.metrics["elbow_angle"] == 90


def test_detector_result_serialises_to_plain_json_types():
    result = DetectorResult("push_ups", 1, "up", {"elbow_angle": 90}, ("Good form",), 0.95)

    assert result.to_dict() == {
        "exercise": "push_ups",
        "reps": 1,
        "stage": "up",
        "metrics": {"elbow_angle": 90},
        "feedback": ["Good form"],
        "confidence": 0.95,
    }


def test_landmark_fixture_satisfies_the_landmark_protocol():
    landmark = FakeLandmark(x=0.1, y=0.2)

    assert math.isclose(landmark.x, 0.1)
    assert landmark.visibility == 1.0
