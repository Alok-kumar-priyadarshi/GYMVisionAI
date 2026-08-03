# file_name: test_detector_rep_adapter.py

"""Unit tests for the detector to RepUpdate adapter."""

from app.engines.exercise.detector_result import DetectorResult
from app.engines.session.detector_rep_adapter import DetectorRepAdapter


def result(reps: int, stage: str | None = "up") -> DetectorResult:
    return DetectorResult("push_ups", reps, stage, {}, (), 1.0)


def test_an_increase_completes_a_repetition():
    adapter = DetectorRepAdapter()

    update = adapter.observe(result(1))

    assert update.rep_completed is True
    assert update.current_rep == 1
    assert update.previous_rep == 0


def test_an_unchanged_count_completes_nothing():
    adapter = DetectorRepAdapter()
    adapter.observe(result(1))

    update = adapter.observe(result(1))

    assert update.rep_completed is False
    assert update.current_rep == 1


def test_successive_repetitions_are_reported_once_each():
    adapter = DetectorRepAdapter()

    completions = [
        adapter.observe(result(reps)).rep_completed for reps in (0, 1, 1, 2, 2, 3)
    ]

    assert completions == [False, True, False, True, False, True]


def test_the_count_never_decreases():
    adapter = DetectorRepAdapter()
    adapter.observe(result(5))

    update = adapter.observe(result(2))

    assert update.current_rep == 5
    assert update.rep_completed is False


def test_the_set_number_is_reported():
    adapter = DetectorRepAdapter()
    adapter.next_set()

    assert adapter.observe(result(1)).current_set == 2


def test_reset_clears_observed_state():
    adapter = DetectorRepAdapter()
    adapter.observe(result(4))
    adapter.next_set()

    adapter.reset()
    update = adapter.observe(result(1))

    assert update.previous_rep == 0
    assert update.current_set == 1


def test_a_timestamp_is_recorded_only_on_completion():
    adapter = DetectorRepAdapter()

    completed = adapter.observe(result(1), timestamp=12.5)
    unchanged = adapter.observe(result(1), timestamp=13.0)

    assert completed.completion_timestamp == 12.5
    assert unchanged.completion_timestamp is None


def test_quality_fields_stay_unpopulated():
    # They need the Form Validation and Movement State engines.
    update = DetectorRepAdapter().observe(result(1))

    assert update.rep_quality is None
    assert update.invalid_reps == 0
    assert update.skipped_reps == 0
    assert update.last_completed_state is None


def test_a_holding_stage_is_recognised():
    assert DetectorRepAdapter.is_holding(result(1, "holding")) is True
    assert DetectorRepAdapter.is_holding(result(1, "adjust_form")) is False
    assert DetectorRepAdapter.is_holding(result(1, None)) is False


def test_updates_serialise_to_plain_types():
    payload = DetectorRepAdapter().observe(result(1)).to_dict()

    assert payload["current_rep"] == 1
    assert payload["rep_completed"] is True
