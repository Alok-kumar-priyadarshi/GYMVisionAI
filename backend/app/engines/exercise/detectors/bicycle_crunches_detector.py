# file_name: bicycle_crunches_detector.py
import math
from app.engines.exercise.base_exercise import BaseExercise


class BicycleCrunchesDetector(BaseExercise):
    UP_THRESHOLD = 30
    DOWN_THRESHOLD = 70
    MIN_VISIBILITY = 0.7

    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26

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
            landmarks[self.RIGHT_SHOULDER].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_KNEE].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_KNEE].visibility > self.MIN_VISIBILITY
        )

        left_dist = abs(landmarks[self.LEFT_SHOULDER].x - landmarks[self.RIGHT_KNEE].x)
        right_dist = abs(landmarks[self.RIGHT_SHOULDER].x - landmarks[self.LEFT_KNEE].x)

        if key_landmarks_visible:
            if left_dist < right_dist:
                active_metric = left_dist
                side = "left"
            else:
                active_metric = right_dist
                side = "right"

            if active_metric < 0.2:
                if self.stage == "down" or self._active_side != side:
                    self.stage = "up"
                    self._active_side = side
            elif active_metric > 0.4 and self.stage == "up":
                self.stage = "down"
                self.reps += 1

        return {
            "reps": self.reps,
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0