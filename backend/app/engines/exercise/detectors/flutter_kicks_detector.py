# file_name: flutter_kicks_detector.py
import math
from app.engines.exercise.base_exercise import BaseExercise


class FlutterKicksDetector(BaseExercise):
    VERTICAL_THRESHOLD = 0.015  # Ankle vertical movement threshold
    MIN_VISIBILITY = 0.7

    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    def __init__(self):
        super().__init__()
        self._prev_left_y = None
        self._prev_right_y = None

    def reset(self) -> None:
        self.reps = 0
        self.stage = "active"
        self._prev_left_y = None
        self._prev_right_y = None

    def process(self, landmarks) -> dict:
        key_landmarks_visible = (
            landmarks[self.LEFT_ANKLE].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_ANKLE].visibility > self.MIN_VISIBILITY
        )

        left_y = landmarks[self.LEFT_ANKLE].y
        right_y = landmarks[self.RIGHT_ANKLE].y

        if key_landmarks_visible:
            if self._prev_left_y is not None and self._prev_right_y is not None:
                left_diff = abs(left_y - self._prev_left_y)
                right_diff = abs(right_y - self._prev_right_y)

                if left_diff > self.VERTICAL_THRESHOLD or right_diff > self.VERTICAL_THRESHOLD:
                    self.reps += 0.5  # Count alternating alternating kick oscillations

            self._prev_left_y = left_y
            self._prev_right_y = right_y

        return {
            "reps": int(self.reps),
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0