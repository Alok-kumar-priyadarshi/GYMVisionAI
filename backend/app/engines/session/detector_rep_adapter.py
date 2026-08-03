# file_name: detector_rep_adapter.py

"""Bridges detector output to the ``RepUpdate`` contract.

``docs/02_runtime/18_WORKOUT_SESSION_ENGINE.md`` section 4 has the session engine
consume ``RepUpdate``, produced by the Rep Counter Engine. That engine is not
implemented: ``docs/02_runtime/16_REP_COUNTER_ENGINE.md`` section 25 requires a
per-exercise FSM definition, valid transition graph and rep duration bounds, and
no document defines those for any exercise.

The detectors already count repetitions, so this adapter turns successive
detector results into ``RepUpdate`` events. It observes rep count changes only.
It performs no FSM cycle validation, which means the quality fields of the
contract stay unpopulated:

- ``rep_quality`` requires the Form Validation Engine.
- ``invalid_reps`` and ``skipped_reps`` require FSM transition validation.
- ``last_completed_state`` requires the Movement State Engine.

This adapter is replaced by the Rep Counter Engine once exercise FSMs are
defined. It exists so the session engine can be driven today.
"""

import logging

from app.engines.exercise.detector_result import DetectorResult
from app.engines.session.runtime_contracts import RepUpdate

logger = logging.getLogger(__name__)


class DetectorRepAdapter:
    """Converts a detector's running rep count into repetition events."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Clear observed state before a new exercise session."""
        self._total_reps = 0
        self._current_set = 1

    def next_set(self) -> None:
        """Advance the set counter reported on subsequent updates."""
        self._current_set += 1

    def observe(
        self, result: DetectorResult, timestamp: float | None = None
    ) -> RepUpdate:
        """Convert one detector result into a repetition update.

        Args:
            result: The detector's analysis of the current frame.
            timestamp: Session time of the observation, in seconds.

        Returns:
            A ``RepUpdate`` whose ``rep_completed`` is true only on the frame
            where the detector's count increased.
        """
        previous = self._total_reps
        # A detector resets to zero between sessions; never report a decrease.
        current = max(previous, result.reps)
        completed = current > previous
        self._total_reps = current

        return RepUpdate(
            current_rep=current,
            previous_rep=previous,
            current_set=self._current_set,
            rep_completed=completed,
            total_reps=current,
            completion_timestamp=timestamp if completed else None,
        )

    @staticmethod
    def is_holding(result: DetectorResult) -> bool:
        """Report whether a detector result shows a held position.

        Hold-based detectors publish ``stage == "holding"`` while the position is
        correct, and a corrective stage otherwise.
        """
        return result.stage == "holding"
