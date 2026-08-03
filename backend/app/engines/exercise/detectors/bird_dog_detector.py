# file_name: bird_dog_detector.py
import math
from app.engines.exercise.base_exercise import BaseExercise


class BirdDogDetector(BaseExercise):
    MIN_VISIBILITY = 0.7

    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    def __init__(self):
        super().__init__()
        self._active_side = None

    def reset(self) -> None:
        self.reps = 0
        self.stage = None
        self._active_side = None

    def process(self, landmarks) -> dict:
        key_landmarks_visible = (
            landmarks[self.LEFT_SHOULDER].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_WRIST].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_ANKLE].visibility > self.MIN_VISIBILITY
        )

        left_extension = abs(landmarks[self.LEFT_WRIST].x - landmarks[self.LEFT_ANKLE].x)
        right_extension = abs(landmarks[self.RIGHT_WRIST].x - landmarks[self.RIGHT_ANKLE].x)

        if key_landmarks_visible:
            if left_extension > right_extension:
                active_ext = left_extension
                side = "left"
            else:
                active_ext = right_extension
                side = "right"

            if active_ext > 0.5:
                if self.stage == "down" or self._active_side != side:
                    self.stage = "extended"
                    self._active_side = side
            elif active_ext < 0.25 and self.stage == "extended":
                self.stage = "down"
                self.reps += 1

        return {
            "reps": self.reps,
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0
    