# file_name: landmarks.py

"""Pose landmark fixtures for detector tests.

Detector tests must be deterministic and must not require MediaPipe, so these
helpers build plain landmark objects that satisfy the ``Landmark`` protocol
declared in ``app.engines.exercise.base_exercise``.
"""

import math
from dataclasses import dataclass
from typing import Mapping

from app.engines.exercise.base_exercise import POSE_LANDMARK_COUNT

Point = tuple[float, float]

# MediaPipe Pose landmark indices used by the detectors.
NOSE = 0
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28

# A plausible upright skeleton, used as the starting point for every fixture.
_STANDING_POSE: dict[int, Point] = {
    0: (0.50, 0.10),
    1: (0.48, 0.09),
    2: (0.47, 0.09),
    3: (0.46, 0.09),
    4: (0.52, 0.09),
    5: (0.53, 0.09),
    6: (0.54, 0.09),
    7: (0.45, 0.10),
    8: (0.55, 0.10),
    9: (0.48, 0.12),
    10: (0.52, 0.12),
    LEFT_SHOULDER: (0.42, 0.25),
    RIGHT_SHOULDER: (0.58, 0.25),
    LEFT_ELBOW: (0.40, 0.40),
    RIGHT_ELBOW: (0.60, 0.40),
    LEFT_WRIST: (0.38, 0.55),
    RIGHT_WRIST: (0.62, 0.55),
    17: (0.37, 0.58),
    18: (0.63, 0.58),
    19: (0.37, 0.59),
    20: (0.63, 0.59),
    21: (0.38, 0.58),
    22: (0.62, 0.58),
    LEFT_HIP: (0.45, 0.55),
    RIGHT_HIP: (0.55, 0.55),
    LEFT_KNEE: (0.45, 0.75),
    RIGHT_KNEE: (0.55, 0.75),
    LEFT_ANKLE: (0.45, 0.95),
    RIGHT_ANKLE: (0.55, 0.95),
    29: (0.44, 0.98),
    30: (0.56, 0.98),
    31: (0.46, 0.98),
    32: (0.54, 0.98),
}


@dataclass
class FakeLandmark:
    """A single pose landmark in normalised image coordinates."""

    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


def build_pose(
    points: Mapping[int, Point] | None = None,
    visibility: float = 1.0,
) -> list[FakeLandmark]:
    """Build a full 33-landmark pose.

    Args:
        points: Coordinates overriding the default standing pose, keyed by
            MediaPipe landmark index.
        visibility: Visibility applied to every landmark.

    Returns:
        A list of 33 landmarks.
    """
    coordinates = dict(_STANDING_POSE)
    if points:
        coordinates.update(points)

    return [
        FakeLandmark(
            x=coordinates[index][0],
            y=coordinates[index][1],
            visibility=visibility,
        )
        for index in range(POSE_LANDMARK_COUNT)
    ]


def limb_points(
    vertex: Point,
    angle_degrees: float,
    radius: float = 0.2,
    distal_degrees: float = 90.0,
) -> tuple[Point, Point]:
    """Position the two joints surrounding a vertex to form an exact angle.

    The distal joint (wrist or ankle) is placed directly below the vertex and the
    proximal joint (shoulder or hip) is rotated away from it by ``angle_degrees``.

    Args:
        vertex: Coordinates of the middle joint, such as an elbow or knee.
        angle_degrees: Desired interior angle at the vertex.
        radius: Distance from the vertex to each surrounding joint.
        distal_degrees: Direction of the distal joint, in degrees.

    Returns:
        A ``(proximal, distal)`` pair of coordinates.
    """
    distal_radians = math.radians(distal_degrees)
    proximal_radians = math.radians(distal_degrees + angle_degrees)

    distal = (
        vertex[0] + radius * math.cos(distal_radians),
        vertex[1] + radius * math.sin(distal_radians),
    )
    proximal = (
        vertex[0] + radius * math.cos(proximal_radians),
        vertex[1] + radius * math.sin(proximal_radians),
    )
    return proximal, distal


def push_up_pose(elbow_angle: float, visibility: float = 1.0) -> list[FakeLandmark]:
    """Build a pose whose left and right elbow angles equal ``elbow_angle``."""
    left_shoulder, left_wrist = limb_points((0.40, 0.40), elbow_angle)
    right_shoulder, right_wrist = limb_points((0.60, 0.40), elbow_angle)

    return build_pose(
        {
            LEFT_SHOULDER: left_shoulder,
            LEFT_WRIST: left_wrist,
            RIGHT_SHOULDER: right_shoulder,
            RIGHT_WRIST: right_wrist,
        },
        visibility=visibility,
    )


def squat_pose(knee_angle: float, visibility: float = 1.0) -> list[FakeLandmark]:
    """Build a pose whose left and right knee angles equal ``knee_angle``."""
    left_hip, left_ankle = limb_points((0.45, 0.75), knee_angle)
    right_hip, right_ankle = limb_points((0.55, 0.75), knee_angle)

    return build_pose(
        {
            LEFT_HIP: left_hip,
            LEFT_ANKLE: left_ankle,
            RIGHT_HIP: right_hip,
            RIGHT_ANKLE: right_ankle,
        },
        visibility=visibility,
    )
