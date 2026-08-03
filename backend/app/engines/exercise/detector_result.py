# file_name: detector_result.py

"""Normalised detector output.

``DetectorResult`` is the single structure every detector exposes to the
application layer, as specified by the Detector Output Contract in
``docs/12_reference/02_DETECTOR_REFERENCE.md``.

Individual detectors return exercise-specific flat dictionaries. ``BaseExercise``
converts those into this contract so that callers never depend on the internal
shape of any one detector.

Per ``docs/02_runtime/12_RUNTIME_CONTRACTS.md`` section 11, runtime contracts are
immutable, serialisable and framework independent. Metric and feedback containers
are therefore read-only.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

CONTRACT_NAME = "DetectorResult"
CONTRACT_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class DetectorResult:
    """One frame of analysis produced by an exercise detector.

    Attributes:
        exercise: Identifier of the exercise that produced the result.
        reps: Completed repetitions counted so far in the session.
        stage: Current movement stage, or ``None`` before the first transition.
        metrics: Exercise-specific measurements keyed in ``snake_case``.
        feedback: Live coaching messages derived from the detector's form checks.
        confidence: Mean landmark visibility for the frame, in the range 0.0-1.0.
    """

    exercise: str
    reps: int
    stage: str | None
    metrics: Mapping[str, Any]
    feedback: tuple[str, ...]
    confidence: float

    def __post_init__(self) -> None:
        # Freeze the mapping so a caller cannot mutate a contract it received.
        if not isinstance(self.metrics, MappingProxyType):
            object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))
        if not isinstance(self.feedback, tuple):
            object.__setattr__(self, "feedback", tuple(self.feedback))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the contract.

        Keys remain ``snake_case``. Converting them to the ``camelCase`` shape of
        ``contracts/exercises/02_PROCESS_FRAME.md`` is the API layer's task.
        """
        return {
            "exercise": self.exercise,
            "reps": self.reps,
            "stage": self.stage,
            "metrics": dict(self.metrics),
            "feedback": list(self.feedback),
            "confidence": self.confidence,
        }
