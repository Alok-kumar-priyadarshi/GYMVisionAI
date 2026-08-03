# file_name: test_rep_validation.py

"""Repetition validation, per ``16_REP_COUNTER_ENGINE.md`` section 11."""

import pytest

from app.engines.session.rep_validation import (
    RepValidationPolicy,
    RepValidator,
)

GOOD = 0.9
"""Confidence comfortably above the threshold."""


@pytest.fixture
def validator() -> RepValidator:
    return RepValidator(
        RepValidationPolicy(minimum_seconds=0.4, confidence_threshold=0.5)
    )


def test_the_first_repetition_is_counted(validator: RepValidator) -> None:
    # Nothing precedes it, so the minimum-interval floor must not block it.
    outcome = validator.observe(raw_reps=1, confidence=GOOD, elapsed_seconds=0.1)

    assert outcome.accepted_reps == 1


def test_repetitions_at_a_human_pace_are_counted(validator: RepValidator) -> None:
    for index, moment in enumerate([0.5, 1.2, 1.9, 2.6], start=1):
        outcome = validator.observe(
            raw_reps=index, confidence=GOOD, elapsed_seconds=moment
        )

    assert outcome.accepted_reps == 4
    assert outcome.rejected_reps == 0


def test_flicker_near_a_threshold_is_rejected(validator: RepValidator) -> None:
    """The reported cause of counts running far ahead of the work done.

    A joint angle resting on a detector's threshold crosses it many times a
    second, and the detector reads every crossing as another repetition.
    """
    validator.observe(raw_reps=1, confidence=GOOD, elapsed_seconds=1.0)

    # Twenty more "repetitions" over a fifth of a second.
    for index in range(2, 22):
        outcome = validator.observe(
            raw_reps=index, confidence=GOOD, elapsed_seconds=1.0 + index * 0.01
        )

    assert outcome.accepted_reps == 1
    assert outcome.rejected_reps == 20


def test_a_poorly_tracked_frame_cannot_complete_a_repetition(
    validator: RepValidator,
) -> None:
    outcome = validator.observe(raw_reps=1, confidence=0.2, elapsed_seconds=1.0)

    assert outcome.accepted_reps == 0
    assert outcome.rejected_reps == 1


def test_only_one_repetition_may_complete_per_frame(
    validator: RepValidator,
) -> None:
    # A jump of five within one frame means the detector's state flapped.
    outcome = validator.observe(raw_reps=5, confidence=GOOD, elapsed_seconds=1.0)

    assert outcome.accepted_reps == 1
    assert outcome.rejected_reps == 4


def test_a_steady_count_adds_nothing(validator: RepValidator) -> None:
    validator.observe(raw_reps=1, confidence=GOOD, elapsed_seconds=1.0)

    # Frames keep arriving while the person holds still.
    for moment in (1.1, 1.2, 1.3, 5.0):
        outcome = validator.observe(
            raw_reps=1, confidence=GOOD, elapsed_seconds=moment
        )

    assert outcome.accepted_reps == 1
    assert outcome.rejected_reps == 0


def test_a_detector_restarting_its_count_is_not_a_negative_jump(
    validator: RepValidator,
) -> None:
    validator.observe(raw_reps=3, confidence=GOOD, elapsed_seconds=3.0)
    before = validator.accepted

    validator.observe(raw_reps=0, confidence=GOOD, elapsed_seconds=3.1)
    outcome = validator.observe(raw_reps=1, confidence=GOOD, elapsed_seconds=4.0)

    # The count already earned is kept, and the restart adds one, not minus two.
    assert outcome.accepted_reps == before + 1


def test_a_pause_between_repetitions_is_allowed(validator: RepValidator) -> None:
    # Only repetitions that are too *fast* are rejected. Resting mid-set is
    # normal, and the maximum-duration gate is deliberately not applied.
    validator.observe(raw_reps=1, confidence=GOOD, elapsed_seconds=1.0)
    outcome = validator.observe(raw_reps=2, confidence=GOOD, elapsed_seconds=45.0)

    assert outcome.accepted_reps == 2


def test_reset_clears_everything(validator: RepValidator) -> None:
    validator.observe(raw_reps=3, confidence=GOOD, elapsed_seconds=2.0)

    validator.reset()

    assert validator.accepted == 0
    assert validator.rejected == 0
    # And the floor must not block the first repetition of the new session.
    assert validator.observe(1, GOOD, 0.05).accepted_reps == 1
