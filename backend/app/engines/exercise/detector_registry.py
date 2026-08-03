# file_name: detector_registry.py

"""Registry mapping exercise identifiers to detector implementations.

Described in ``docs/04_backend/28_BACKEND_ARCHITECTURE.md`` section 18. The
registry centralises detector management and removes long ``if/elif`` chains from
the application layer.

Only the exercises listed in ``docs/12_reference/01_SUPPORTED_EXERCISES.md`` are
registered. An exercise without a registered detector is not supported, and the
application layer must reject it rather than fall back to another detector.
"""

import logging
from typing import Mapping

from app.engines.exercise.base_exercise import BaseExercise
from app.engines.exercise.detectors.bicycle_crunches_detector import (
    BicycleCrunchesDetector,
)
from app.engines.exercise.detectors.bird_dog_detector import BirdDogDetector
from app.engines.exercise.detectors.bodyweight_squats_detector import (
    BodyweightSquatsDetector,
)
from app.engines.exercise.detectors.burpees_detector import BurpeesDetector
from app.engines.exercise.detectors.butt_kicks_detector import ButtKicksDetector
from app.engines.exercise.detectors.calf_raises_detector import CalfRaisesDetector
from app.engines.exercise.detectors.dead_bug_detector import DeadBugDetector
from app.engines.exercise.detectors.flutter_kicks_detector import FlutterKicksDetector
from app.engines.exercise.detectors.forward_lunges_detector import ForwardLungesDetector
from app.engines.exercise.detectors.glute_bridges_detector import GluteBridgesDetector
from app.engines.exercise.detectors.high_knees_detector import HighKneesDetector
from app.engines.exercise.detectors.hip_circles_detector import HipCirclesDetector
from app.engines.exercise.detectors.incline_push_ups_detector import (
    InclinePushUpsDetector,
)
from app.engines.exercise.detectors.jumping_jacks_detector import JumpingJacksDetector
from app.engines.exercise.detectors.knee_push_ups_detector import KneePushUpsDetector
from app.engines.exercise.detectors.leg_raises_detector import LegRaisesDetector
from app.engines.exercise.detectors.mountain_climbers_detector import (
    MountainClimbersDetector,
)
from app.engines.exercise.detectors.pike_push_ups_detector import PikePushUpsDetector
from app.engines.exercise.detectors.plank_detector import PlankDetector
from app.engines.exercise.detectors.push_ups_detector import PushUpsDetector
from app.engines.exercise.detectors.reverse_lunges_detector import ReverseLungesDetector
from app.engines.exercise.detectors.russian_twists_detector import RussianTwistsDetector
from app.engines.exercise.detectors.side_lunges_detector import SideLungesDetector
from app.engines.exercise.detectors.side_plank_detector import SidePlankDetector
from app.engines.exercise.detectors.single_leg_glute_bridges_detector import (
    SingleLegGluteBridgesDetector,
)
from app.engines.exercise.detectors.step_ups_detector import StepUpsDetector
from app.engines.exercise.detectors.sumo_squats_detector import SumoSquatsDetector
from app.engines.exercise.detectors.triceps_dips_detector import TricepsDipsDetector
from app.engines.exercise.detectors.wall_sit_detector import WallSitDetector
from app.shared.exceptions import DetectorUnavailableError, UnsupportedExerciseError

logger = logging.getLogger(__name__)


DETECTORS: Mapping[str, type[BaseExercise]] = {
    # Warm-up
    "jumping_jacks": JumpingJacksDetector,
    "high_knees": HighKneesDetector,
    "butt_kicks": ButtKicksDetector,
    "hip_circles": HipCirclesDetector,
    # Lower Body
    "bodyweight_squats": BodyweightSquatsDetector,
    "sumo_squats": SumoSquatsDetector,
    "reverse_lunges": ReverseLungesDetector,
    "forward_lunges": ForwardLungesDetector,
    "side_lunges": SideLungesDetector,
    "glute_bridges": GluteBridgesDetector,
    "single_leg_glute_bridges": SingleLegGluteBridgesDetector,
    "wall_sit": WallSitDetector,
    "calf_raises": CalfRaisesDetector,
    "step_ups": StepUpsDetector,
    # Upper Body
    "push_ups": PushUpsDetector,
    "knee_push_ups": KneePushUpsDetector,
    "incline_push_ups": InclinePushUpsDetector,
    "pike_push_ups": PikePushUpsDetector,
    "triceps_dips": TricepsDipsDetector,
    # Core
    "plank": PlankDetector,
    "side_plank": SidePlankDetector,
    "bicycle_crunches": BicycleCrunchesDetector,
    "mountain_climbers": MountainClimbersDetector,
    "dead_bug": DeadBugDetector,
    "bird_dog": BirdDogDetector,
    "leg_raises": LegRaisesDetector,
    "russian_twists": RussianTwistsDetector,
    "flutter_kicks": FlutterKicksDetector,
    # Full Body
    "burpees": BurpeesDetector,
}
"""Every supported exercise identifier mapped to its detector implementation."""


HOLD_BASED_EXERCISES: frozenset[str] = frozenset(
    {"plank", "side_plank", "wall_sit"}
)
"""Exercises measured by hold duration rather than repetitions.

These detectors report ``stage`` only. Accumulating hold time from frame
timestamps belongs to the exercise session service, because a detector receives
no timing information.
"""


class DetectorRegistry:
    """Creates detector instances for supported exercises."""

    @staticmethod
    def is_supported(exercise_id: str) -> bool:
        """Report whether an exercise has a registered detector."""
        return exercise_id in DETECTORS

    @staticmethod
    def supported_exercises() -> tuple[str, ...]:
        """Return every supported exercise identifier, in registration order."""
        return tuple(DETECTORS)

    @staticmethod
    def detector_class(exercise_id: str) -> type[BaseExercise]:
        """Return the detector class registered for an exercise.

        Args:
            exercise_id: Identifier of a supported exercise.

        Returns:
            The registered detector class.

        Raises:
            UnsupportedExerciseError: If no detector is registered.
        """
        try:
            return DETECTORS[exercise_id]
        except KeyError as error:
            logger.warning("Detector requested for unsupported exercise.")
            raise UnsupportedExerciseError(
                f"Exercise '{exercise_id}' is not supported."
            ) from error

    @classmethod
    def create(cls, exercise_id: str) -> BaseExercise:
        """Create a detector instance ready to analyse a new session.

        Args:
            exercise_id: Identifier of a supported exercise.

        Returns:
            A detector instance with repetition count and stage reset.

        Raises:
            UnsupportedExerciseError: If no detector is registered.
            DetectorUnavailableError: If the registered detector cannot start.
        """
        detector_class = cls.detector_class(exercise_id)
        try:
            return detector_class()
        except Exception as error:
            logger.exception("Detector '%s' failed to initialise.", exercise_id)
            raise DetectorUnavailableError(
                f"Detector for exercise '{exercise_id}' is unavailable."
            ) from error
