# file_name: arm_circles_detector.py

import math
from app.engines.exercise.base_exercise import BaseExercise


class ArmCirclesDetector(BaseExercise):
    MIN_VISIBILITY = 0.7
    ROTATION_THRESHOLD = 360  # Tracking full rotational cycles

    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_WRIST = 15
    RIGHT_WRIST = 16

    def __init__(self):
        super().__init__()
        self._prev_wrist_angle = 0.0

    def reset(self) -> None:
        self.reps = 0
        self.stage = "active"
        self._prev_wrist_angle = 0.0

    def process(self, landmarks) -> dict:
        key_landmarks_visible = (
            landmarks[self.LEFT_SHOULDER].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_SHOULDER].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_WRIST].visibility > self.MIN_VISIBILITY
        )

        shoulder = self.get_point(landmarks, self.LEFT_SHOULDER)
        wrist = self.get_point(landmarks, self.LEFT_WRIST)

        dx = wrist[0] - shoulder[0]
        dy = wrist[1] - shoulder[1]
        current_angle = math.degrees(math.atan2(dy, dx))

        if key_landmarks_visible:
            angle_diff = current_angle - self._prev_wrist_angle
            if angle_diff > 180:
                angle_diff -= 360
            elif angle_diff < -180:
                angle_diff += 360

            self.reps += abs(angle_diff) / 360
            self._prev_wrist_angle = current_angle

        return {
            "reps": int(self.reps),
            "current_angle": int(current_angle),
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0