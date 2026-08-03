# file_name: wall_sit_detector.py

import math
from app.engines.exercise.base_exercise import BaseExercise


class WallSitDetector(BaseExercise):
    TARGET_KNEE_ANGLE = 90
    ANGLE_TOLERANCE = 15
    MIN_VISIBILITY = 0.7

    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    def __init__(self):
        super().__init__()
        self.duration_seconds = 0.0

    def reset(self) -> None:
        self.reps = 0
        self.stage = None
        self.duration_seconds = 0.0

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

        avg_knee_angle = (left_knee_angle + right_knee_angle) / 2

        if key_landmarks_visible:
            if abs(avg_knee_angle - self.TARGET_KNEE_ANGLE) <= self.ANGLE_TOLERANCE:
                self.stage = "holding"
                self.reps = 1  # Holding counts as active metric representation
                form_status = "GOOD HOLD"
            else:
                self.stage = "adjust"
                form_status = "ADJUST KNEE ANGLE TO 90 DEG"
        else:
            form_status = "POSITION NOT VISIBLE"

        return {
            "reps": self.reps,
            "knee_angle": int(avg_knee_angle),
            "form_status": form_status,
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0
    