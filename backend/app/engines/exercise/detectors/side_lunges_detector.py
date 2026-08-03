# file_name: side_lunges_detector.py

import math
from app.engines.exercise.base_exercise import BaseExercise


class SideLungesDetector(BaseExercise):
    UP_THRESHOLD = 160
    DOWN_THRESHOLD = 100
    MIN_VISIBILITY = 0.7

    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    def __init__(self):
        super().__init__()
        self._active_leg = None

    def reset(self) -> None:
        self.reps = 0
        self.stage = None
        self._active_leg = None

    def process(self, landmarks) -> dict:
        key_landmarks_visible = (
            landmarks[self.LEFT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_KNEE].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_KNEE].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_ANKLE].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_ANKLE].visibility > self.MIN_VISIBILITY
        )

        left_knee_angle = self.calculate_angle(
            self.get_point(landmarks, self.LEFT_HIP),
            self.get_point(landmarks, self.LEFT_KNEE),
            self.get_point(landmarks, self.LEFT_ANKLE)
        )

        right_knee_angle = self.calculate_angle(
            self.get_point(landmarks, self.RIGHT_HIP),
            self.get_point(landmarks, self.RIGHT_KNEE),
            self.get_point(landmarks, self.RIGHT_ANKLE)
        )

        if key_landmarks_visible:
            if left_knee_angle < right_knee_angle:
                active_angle = left_knee_angle
                leg = "left"
            else:
                active_angle = right_knee_angle
                leg = "right"

            if active_angle > self.UP_THRESHOLD:
                self.stage = "up"

            if active_angle < self.DOWN_THRESHOLD and self.stage == "up":
                self.stage = "down"
                self.reps += 1
                self._active_leg = leg

        return {
            "reps": self.reps,
            "left_knee_angle": int(left_knee_angle),
            "right_knee_angle": int(right_knee_angle),
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0
    
    