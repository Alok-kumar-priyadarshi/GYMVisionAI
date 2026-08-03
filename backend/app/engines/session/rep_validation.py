# file_name: rep_validation.py

"""Validation of repetitions reported by a detector.

``docs/02_runtime/16_REP_COUNTER_ENGINE.md`` section 11 counts a repetition only
when every required state was visited, every transition was valid, the minimum
completion time is satisfied, the maximum is not exceeded, and the required
confidence is met.

The full engine is not implemented: section 25 requires a per-exercise FSM
definition and transition graph, and no document defines those, so the detectors
still do the counting (see ``detector_rep_adapter``). Two of section 11's gates
need no FSM, and those are applied here:

- **Minimum completion time.** Landmarks are noisy. A joint angle sitting near a
  detector's threshold flickers across it many times a second, and every flicker
  the detector reads as another repetition. This is the cause of counts running
  far ahead of the work actually done.
- **Required confidence.** A frame where the body is poorly tracked is not
  evidence that a repetition happened.

The maximum completion time is deliberately *not* applied. It bounds one FSM
cycle, and without the FSM the only measurable interval is the gap since the
previous accepted repetition. Someone pausing between repetitions would have
their next good repetition thrown away, so applying it here would invent a rule
the documentation does not ask for.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_MINIMUM_SECONDS = 0.4
"""Floor on the time between two counted repetitions.

Nothing a person does with their whole body repeats faster than this. Detector
noise repeats far faster, which is exactly what the floor removes.
"""

DEFAULT_CONFIDENCE_THRESHOLD = 0.5
"""Mean landmark visibility a frame needs before it may complete a repetition.

Matches the threshold the camera page already uses to decide that tracking has
been lost, so the two agree about what "in shot" means.
"""


@dataclass(frozen=True, slots=True)
class RepValidationPolicy:
    """The bounds a repetition is judged against.

    Per-exercise values belong in configuration once the FSM definitions
    required by section 25 exist. Until then these are engine-wide defaults,
    which keeps the engine free of exercise-specific constants as section 26
    requires.
    """

    minimum_seconds: float = DEFAULT_MINIMUM_SECONDS
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD


@dataclass
class RepValidationOutcome:
    """What the validator made of one frame."""

    accepted_reps: int
    """Cumulative count of repetitions that passed validation."""

    rejected_reps: int
    """Cumulative count the detector reported but validation refused."""


class RepValidator:
    """Filters a detector's running rep count down to credible repetitions.

    The detector reports a cumulative total. This observes the increases in that
    total and decides which of them to believe, so it never has to know how any
    particular detector works.
    """

    def __init__(self, policy: RepValidationPolicy | None = None) -> None:
        self._policy = policy or RepValidationPolicy()
        self.reset()

    def reset(self) -> None:
        """Clear all state before a new session."""
        self._last_seen_raw = 0
        self._accepted = 0
        self._rejected = 0
        # Negative so the first repetition is never blocked by the floor: there
        # is no previous repetition for it to be too close to.
        self._last_accepted_at = float("-inf")

    @property
    def accepted(self) -> int:
        """Repetitions counted so far."""
        return self._accepted

    @property
    def rejected(self) -> int:
        """Repetitions the detector claimed that were not counted."""
        return self._rejected

    def observe(
        self, raw_reps: int, confidence: float, elapsed_seconds: float
    ) -> RepValidationOutcome:
        """Judge the detector's latest cumulative count.

        Args:
            raw_reps: The detector's running total for the session.
            confidence: Mean visibility of the landmarks this detector needs.
            elapsed_seconds: Session time at which the frame was analysed.

        Returns:
            The cumulative accepted and rejected totals.
        """
        # A detector that restarts its count (a reset mid-session) must not be
        # read as a large negative jump.
        if raw_reps < self._last_seen_raw:
            self._last_seen_raw = raw_reps

        claimed = raw_reps - self._last_seen_raw
        self._last_seen_raw = raw_reps

        if claimed <= 0:
            return self._outcome()

        # At most one repetition can complete in the instant of a single frame.
        # A jump of several means the detector's state flapped between frames,
        # and only one of those can be credited.
        if claimed > 1:
            self._rejected += claimed - 1
            logger.debug("Detector claimed %d repetitions in one frame.", claimed)

        if confidence < self._policy.confidence_threshold:
            self._rejected += 1
            return self._outcome()

        if elapsed_seconds - self._last_accepted_at < self._policy.minimum_seconds:
            self._rejected += 1
            return self._outcome()

        self._accepted += 1
        self._last_accepted_at = elapsed_seconds
        return self._outcome()

    def _outcome(self) -> RepValidationOutcome:
        return RepValidationOutcome(
            accepted_reps=self._accepted, rejected_reps=self._rejected
        )
