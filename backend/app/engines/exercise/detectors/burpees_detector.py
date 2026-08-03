# file_name: burpees_detector.py
import math
from app.engines.exercise.base_exercise import BaseExercise


class BurpeesDetector(BaseExercise):
    DOWN_THRESHOLD = 0.15  # Floor level proximity or hip drop threshold
    UP_THRESHOLD = 0.05    # Standing tall threshold
    MIN_VISIBILITY = 0.7

    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12

    def __init__(self):
        super().__init__()

    def reset(self) -> None:
        self.reps = 0
        self.stage = "standing"

    def process(self, landmarks) -> dict:
        key_landmarks_visible = (
            landmarks[self.LEFT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_SHOULDER].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_SHOULDER].visibility > self.MIN_VISIBILITY
        )

        hip_y = (landmarks[self.LEFT_HIP].y + landmarks[self.RIGHT_HIP].y) / 2
        shoulder_y = (landmarks[self.LEFT_SHOULDER].y + landmarks[self.RIGHT_SHOULDER].y) / 2

        if key_landmarks_visible:
            # In MediaPipe, higher pixel Y values mean lower position relative to the camera frame (ground level)
            if hip_y > 0.65:  # Dropped down / plank / push-up position
                self.stage = "down"
            elif hip_y < 0.45 and self.stage == "down":  # Jumped up / standing tall
                self.stage = "standing"
                self.reps += 1

        return {
            "reps": self.reps,
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0