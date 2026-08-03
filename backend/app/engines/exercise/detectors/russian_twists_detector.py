# file_name: russian_twists_detector.py
import math
from app.engines.exercise.base_exercise import BaseExercise


class RussianTwistsDetector(BaseExercise):
    TWIST_THRESHOLD = 0.08  # Horizontal displacement threshold for shoulder rotation
    MIN_VISIBILITY = 0.7

    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24

    def __init__(self):
        super().__init__()
        self._last_side = None

    def reset(self) -> None:
        self.reps = 0
        self.stage = None
        self._last_side = None

    def process(self, landmarks) -> dict:
        key_landmarks_visible = (
            landmarks[self.LEFT_SHOULDER].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_SHOULDER].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_HIP].visibility > self.MIN_VISIBILITY
        )

        shoulder_mid_x = (landmarks[self.LEFT_SHOULDER].x + landmarks[self.RIGHT_SHOULDER].x) / 2
        hip_mid_x = (landmarks[self.LEFT_HIP].x + landmarks[self.RIGHT_HIP].x) / 2

        diff_x = shoulder_mid_x - hip_mid_x

        if key_landmarks_visible:
            if diff_x > self.TWIST_THRESHOLD:
                self.stage = "right_twist"
                if self._last_side == "left":
                    self.reps += 0.5
                    self._last_side = "right"
                elif self._last_side is None:
                    self._last_side = "right"
            elif diff_x < -self.TWIST_THRESHOLD:
                self.stage = "left_twist"
                if self._last_side == "right":
                    self.reps += 0.5
                    self._last_side = "left"
                elif self._last_side is None:
                    self._last_side = "left"

        return {
            "reps": int(self.reps),
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0
    
    