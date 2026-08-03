# file_name: __init__.py

"""Exercise detector engine.

Public surface of the engine. The application layer depends on these names only,
never on individual detector modules.
"""

from app.engines.exercise.base_exercise import (
    POSE_LANDMARK_COUNT,
    BaseExercise,
    Landmark,
)
from app.engines.exercise.detector_registry import (
    DETECTORS,
    HOLD_BASED_EXERCISES,
    DetectorRegistry,
)
from app.engines.exercise.detector_result import DetectorResult

__all__ = [
    "POSE_LANDMARK_COUNT",
    "BaseExercise",
    "DETECTORS",
    "DetectorRegistry",
    "DetectorResult",
    "HOLD_BASED_EXERCISES",
    "Landmark",
]
