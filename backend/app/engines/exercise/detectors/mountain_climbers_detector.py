# file_name: mountain_climbers_detector.py
import math
from app.engines.exercise.base_exercise import BaseExercise


class MountainClimbersDetector(BaseExercise):
    UP_THRESHOLD = 0.15  # Knee pulled close to chest distance threshold
    DOWN_THRESHOLD = 0.35  # Leg extended back threshold
    MIN_VISIBILITY = 0.7

    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26

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
            landmarks[self.RIGHT_KNEE].visibility > self.MIN_VISIBILITY
        )

        left_knee_to_hip_dist = abs(landmarks[self.LEFT_KNEE].y - landmarks[self.LEFT_HIP].y)
        right_knee_to_hip_dist = abs(landmarks[self.RIGHT_KNEE].y - landmarks[self.RIGHT_HIP].y)

        if key_landmarks_visible:
            if left_knee_to_hip_dist < right_knee_to_hip_dist:
                active_dist = left_knee_to_hip_dist
                leg = "left"
            else:
                active_dist = right_knee_to_hip_dist
                leg = "right"

            if active_dist < self.UP_THRESHOLD:
                if self.stage == "down" or self._active_leg != leg:
                    self.stage = "up"
                    self._active_leg = leg

            if active_dist > self.DOWN_THRESHOLD and self.stage == "up":
                self.stage = "down"
                self.reps += 1

        return {
            "reps": self.reps,
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0
    
    