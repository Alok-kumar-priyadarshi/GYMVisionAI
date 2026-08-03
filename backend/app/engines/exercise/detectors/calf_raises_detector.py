# file_name: calf_raises_detector.py

import math
from app.engines.exercise.base_exercise import BaseExercise


class CalfRaisesDetector(BaseExercise):
    UP_THRESHOLD = 0.05   # Ankle y-position shift upward relative to hip/knee base
    DOWN_THRESHOLD = 0.01
    MIN_VISIBILITY = 0.7

    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    def __init__(self):
        super().__init__()
        self._ankle_y_baseline = None

    def reset(self) -> None:
        self.reps = 0
        self.stage = None
        self._ankle_y_baseline = None

    def process(self, landmarks) -> dict:
        key_landmarks_visible = (
            landmarks[self.LEFT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_ANKLE].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_ANKLE].visibility > self.MIN_VISIBILITY
        )

        left_ankle_y = landmarks[self.LEFT_ANKLE].y
        right_ankle_y = landmarks[self.RIGHT_ANKLE].y
        avg_ankle_y = (left_ankle_y + right_ankle_y) / 2

        if self._ankle_y_baseline is None and key_landmarks_visible:
            self._ankle_y_baseline = avg_ankle_y

        if key_landmarks_visible and self._ankle_y_baseline is not None:
            # In image coordinates, smaller y means higher position
            y_diff = self._ankle_y_baseline - avg_ankle_y

            if y_diff > self.UP_THRESHOLD:
                self.stage = "up"

            if y_diff < self.DOWN_THRESHOLD and self.stage == "up":
                self.stage = "down"
                self.reps += 1

        return {
            "reps": self.reps,
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0
    
    