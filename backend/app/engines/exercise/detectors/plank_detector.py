# file_name: plank_detector.py
import math
from app.engines.exercise.base_exercise import BaseExercise


class PlankDetector(BaseExercise):
    MIN_VISIBILITY = 0.7
    ALIGNMENT_TOLERANCE = 0.05  # Tolerance for shoulder-hip-ankle straight line

    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    def __init__(self):
        super().__init__()

    def reset(self) -> None:
        self.reps = 0
        self.stage = None

    def process(self, landmarks) -> dict:
        key_landmarks_visible = (
            landmarks[self.LEFT_SHOULDER].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_ANKLE].visibility > self.MIN_VISIBILITY
        )

        shoulder_y = landmarks[self.LEFT_SHOULDER].y
        hip_y = landmarks[self.LEFT_HIP].y
        ankle_y = landmarks[self.LEFT_ANKLE].y

        # Check alignment of shoulder, hip, and ankle y-coordinates for a flat back
        # Ideal straight line expectation for a plank position
        expected_hip_y = (shoulder_y + ankle_y) / 2
        hip_deviation = abs(hip_y - expected_hip_y)

        if key_landmarks_visible:
            if hip_deviation <= self.ALIGNMENT_TOLERANCE:
                self.stage = "holding"
                self.reps = 1
            else:
                self.stage = "adjust_form"

        return {
            "reps": self.reps,
            "hip_deviation": round(hip_deviation, 3),
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0