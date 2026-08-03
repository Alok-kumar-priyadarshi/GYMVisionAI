# file_name: leg_raises_detector.py
import math
from app.engines.exercise.base_exercise import BaseExercise


class LegRaisesDetector(BaseExercise):
    UP_THRESHOLD = 70   # Angle of leg relative to hip/vertical when raised high
    DOWN_THRESHOLD = 140 # Legs resting down / extended
    MIN_VISIBILITY = 0.7

    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12

    def __init__(self):
        super().__init__()

    def reset(self) -> None:
        self.reps = 0
        self.stage = None

    def process(self, landmarks) -> dict:
        key_landmarks_visible = (
            landmarks[self.LEFT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_KNEE].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_KNEE].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_SHOULDER].visibility > self.MIN_VISIBILITY
        )

        left_leg_angle = self.calculate_angle(
            self.get_point(landmarks, self.LEFT_SHOULDER),
            self.get_point(landmarks, self.LEFT_HIP),
            self.get_point(landmarks, self.LEFT_KNEE)
        )

        right_leg_angle = self.calculate_angle(
            self.get_point(landmarks, self.RIGHT_SHOULDER),
            self.get_point(landmarks, self.RIGHT_HIP),
            self.get_point(landmarks, self.RIGHT_KNEE)
        )

        avg_leg_angle = (left_leg_angle + right_leg_angle) / 2

        if key_landmarks_visible:
            if avg_leg_angle < self.UP_THRESHOLD:
                self.stage = "up"

            if avg_leg_angle > self.DOWN_THRESHOLD and self.stage == "up":
                self.stage = "down"
                self.reps += 1

        return {
            "reps": self.reps,
            "leg_angle": int(avg_leg_angle),
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0