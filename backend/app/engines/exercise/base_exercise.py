# file_name: base_exercise.py

"""Common base class for every exercise detector.

``BaseExercise`` owns the functionality shared by all detectors, as required by
``docs/04_backend/28_BACKEND_ARCHITECTURE.md`` section 11 and
``docs/12_reference/02_DETECTOR_REFERENCE.md``:

- angle calculation
- landmark extraction
- distance calculation
- shared runtime state (``reps`` and ``stage``)
- normalisation of detector output into :class:`DetectorResult`

The engine is deliberately free of framework dependencies. It never imports
MediaPipe, FastAPI, SQLAlchemy or any AI SDK, and it never touches the database.
Landmarks arrive as plain objects exposing ``x``, ``y``, ``z`` and ``visibility``.
"""

import math
import re
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Protocol, Sequence, runtime_checkable

from app.engines.exercise.detector_result import DetectorResult
from app.shared.exceptions import InvalidLandmarksError

POSE_LANDMARK_COUNT = 33
"""Number of landmarks produced by MediaPipe Pose."""

Point = tuple[float, float]

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


@runtime_checkable
class Landmark(Protocol):
    """Structural type of a single MediaPipe pose landmark."""

    x: float
    y: float
    z: float
    visibility: float


class BaseExercise(ABC):
    """Base class every exercise detector inherits from.

    Subclasses implement exactly two methods:

    ``reset()``
        Clears repetition count, stage and any detector-specific state.
        It is called once from ``__init__`` and again before each new session, so
        it must only assign state and never read state assigned elsewhere.

    ``process(landmarks)``
        Analyses one frame and returns a flat, exercise-specific dictionary.

    Callers should invoke :meth:`analyze` rather than :meth:`process` directly:
    ``analyze`` validates the frame and converts the detector's flat dictionary
    into the documented :class:`DetectorResult` contract.
    """

    EXERCISE_ID: ClassVar[str] = ""
    """Optional explicit identifier. When empty it is derived from the class name."""

    MIN_VISIBILITY: ClassVar[float] = 0.7
    """Default visibility below which a landmark is considered untracked."""

    REQUIRED_LANDMARKS: ClassVar[tuple[int, ...]] = ()
    """Landmarks that determine confidence. Empty means score the whole skeleton."""

    _RESERVED_KEYS: ClassVar[frozenset[str]] = frozenset({"reps", "stage"})
    """Keys consumed directly by the contract rather than exposed as metrics."""

    _STATUS_SUFFIX: ClassVar[str] = "_status"
    """Suffix marking a raw key whose value is a human-readable form assessment."""

    def __init__(self) -> None:
        self.exercise_id: str = self.EXERCISE_ID or self._derive_exercise_id()
        self.reps: float = 0
        self.stage: str | None = None
        self.reset()

    # ------------------------------------------------------------------
    # Detector interface
    # ------------------------------------------------------------------

    @abstractmethod
    def reset(self) -> None:
        """Reset the detector so it can be reused for a new exercise session."""

    @abstractmethod
    def process(self, landmarks: Sequence[Landmark]) -> dict[str, Any]:
        """Analyse one frame and return exercise-specific values.

        Args:
            landmarks: The 33 MediaPipe pose landmarks for the current frame.

        Returns:
            A flat dictionary containing at least ``reps`` and ``stage``.
        """

    def analyze(self, landmarks: Sequence[Landmark]) -> DetectorResult:
        """Validate a frame, run the detector and normalise its output.

        Args:
            landmarks: The 33 MediaPipe pose landmarks for the current frame.

        Returns:
            The frame's analysis in the documented detector output contract.

        Raises:
            InvalidLandmarksError: If the frame does not carry a usable skeleton.
        """
        self.validate_landmarks(landmarks)
        raw_result = self.process(landmarks)
        return self._to_result(raw_result, landmarks)

    # ------------------------------------------------------------------
    # Landmark utilities
    # ------------------------------------------------------------------

    @staticmethod
    def validate_landmarks(landmarks: Sequence[Landmark]) -> None:
        """Ensure a frame carries a complete, well-formed pose skeleton.

        Args:
            landmarks: Candidate landmark collection.

        Raises:
            InvalidLandmarksError: If the collection is missing, too short or
                does not expose the required landmark attributes.
        """
        if landmarks is None:
            raise InvalidLandmarksError("Pose landmarks are required.")

        try:
            landmark_count = len(landmarks)
        except TypeError as error:
            raise InvalidLandmarksError("Pose landmarks must be a sequence.") from error

        if landmark_count < POSE_LANDMARK_COUNT:
            raise InvalidLandmarksError(
                f"Expected {POSE_LANDMARK_COUNT} pose landmarks, received {landmark_count}."
            )

        first = landmarks[0]
        if not all(hasattr(first, attribute) for attribute in ("x", "y", "visibility")):
            raise InvalidLandmarksError(
                "Pose landmarks must expose x, y and visibility values."
            )

    @staticmethod
    def get_point(landmarks: Sequence[Landmark], index: int) -> Point:
        """Return the 2D coordinates of one landmark.

        Args:
            landmarks: The pose landmarks for the current frame.
            index: MediaPipe landmark index.

        Returns:
            The landmark's ``(x, y)`` coordinates in normalised image space.
        """
        landmark = landmarks[index]
        return (landmark.x, landmark.y)

    @staticmethod
    def calculate_angle(first: Point, mid: Point, last: Point) -> float:
        """Return the angle at ``mid`` formed by the three points, in degrees.

        Args:
            first: Coordinates of the first joint.
            mid: Coordinates of the vertex joint.
            last: Coordinates of the third joint.

        Returns:
            The interior angle in the range 0.0-180.0 degrees.
        """
        radians = math.atan2(last[1] - mid[1], last[0] - mid[0]) - math.atan2(
            first[1] - mid[1], first[0] - mid[0]
        )
        angle = abs(math.degrees(radians))
        if angle > 180.0:
            angle = 360.0 - angle
        return angle

    @staticmethod
    def calculate_distance(first: Point, second: Point) -> float:
        """Return the Euclidean distance between two points."""
        return math.hypot(second[0] - first[0], second[1] - first[1])

    @staticmethod
    def midpoint(first: Point, second: Point) -> Point:
        """Return the point halfway between two points."""
        return ((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)

    def is_visible(self, landmarks: Sequence[Landmark], *indices: int) -> bool:
        """Report whether every requested landmark is tracked reliably.

        Args:
            landmarks: The pose landmarks for the current frame.
            *indices: MediaPipe landmark indices to check.

        Returns:
            ``True`` when every landmark's visibility exceeds ``MIN_VISIBILITY``.
        """
        return all(
            landmarks[index].visibility > self.MIN_VISIBILITY for index in indices
        )

    # ------------------------------------------------------------------
    # Output normalisation
    # ------------------------------------------------------------------

    def _to_result(
        self, raw_result: dict[str, Any], landmarks: Sequence[Landmark]
    ) -> DetectorResult:
        """Convert a detector's flat dictionary into the documented contract."""
        return DetectorResult(
            exercise=self.exercise_id,
            reps=self._extract_reps(raw_result),
            stage=raw_result.get("stage"),
            metrics=self._extract_metrics(raw_result),
            feedback=self._extract_feedback(raw_result),
            confidence=self._calculate_confidence(landmarks),
        )

    def _extract_reps(self, raw_result: dict[str, Any]) -> int:
        """Return the completed repetition count as a whole number.

        Detectors that accumulate partial repetitions, such as alternating or
        rotational movements, hold a float internally. Only completed repetitions
        are reported.
        """
        reps = raw_result.get("reps", self.reps)
        try:
            return int(reps)
        except (TypeError, ValueError):
            return 0

    def _extract_metrics(self, raw_result: dict[str, Any]) -> dict[str, Any]:
        """Return every exercise-specific measurement produced by the detector."""
        return {
            key: value
            for key, value in raw_result.items()
            if key not in self._RESERVED_KEYS
        }

    def _extract_feedback(self, raw_result: dict[str, Any]) -> tuple[str, ...]:
        """Derive live coaching messages from the detector's form assessments.

        Any key ending in ``_status`` holds a human-readable assessment such as
        ``"KNEES CAVING IN"``. Those values become the frame's feedback messages
        while remaining available as metrics.
        """
        messages = [
            value.strip().capitalize()
            for key, value in raw_result.items()
            if key.endswith(self._STATUS_SUFFIX)
            and isinstance(value, str)
            and value.strip()
        ]
        return tuple(messages)

    def _calculate_confidence(self, landmarks: Sequence[Landmark]) -> float:
        """Return mean visibility across the landmarks this detector depends on."""
        indices = self.REQUIRED_LANDMARKS or range(len(landmarks))
        visibilities = [landmarks[index].visibility for index in indices]
        if not visibilities:
            return 0.0
        return round(sum(visibilities) / len(visibilities), 4)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @classmethod
    def _derive_exercise_id(cls) -> str:
        """Derive the exercise identifier from the detector's class name.

        ``PushUpsDetector`` becomes ``push_ups``. Detectors whose class name does
        not map cleanly may override ``EXERCISE_ID`` instead.
        """
        name = cls.__name__.removesuffix("Detector")
        return _CAMEL_BOUNDARY.sub("_", name).lower()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(exercise_id={self.exercise_id!r}, reps={int(self.reps)}, stage={self.stage!r})"
        )
