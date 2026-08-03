# file_name: hip_circles_detector.py

import math
from app.engines.exercise.base_exercise import BaseExercise


class HipCirclesDetector(BaseExercise):
    MIN_VISIBILITY = 0.7

    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12

    def __init__(self):
        super().__init__()
        self._prev_angle = 0.0
        self._accumulated_rotation = 0.0

    def reset(self) -> None:
        self.reps = 0
        self.stage = "active"
        self._prev_angle = 0.0
        self._accumulated_rotation = 0.0

    def process(self, landmarks) -> dict:
        key_landmarks_visible = (
            landmarks[self.LEFT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_SHOULDER].visibility > self.MIN_VISIBILITY
        )

        left_hip = self.get_point(landmarks, self.LEFT_HIP)
        right_hip = self.get_point(landmarks, self.RIGHT_HIP)
        
        hip_mid_x = (left_hip[0] + right_hip[0]) / 2
        hip_mid_y = (left_hip[1] + right_hip[1]) / 2

        shoulder_mid_x = (landmarks[self.LEFT_SHOULDER].x + landmarks[self.RIGHT_SHOULDER].x) / 2
        shoulder_mid_y = (landmarks[self.LEFT_SHOULDER].y + landmarks[self.RIGHT_SHOULDER].y) / 2

        dx = hip_mid_x - shoulder_mid_x
        dy = hip_mid_y - shoulder_mid_y
        current_angle = math.degrees(math.atan2(dy, dx))

        if key_landmarks_visible:
            angle_diff = current_angle - self._prev_angle
            if angle_diff > 180:
                angle_diff -= 360
            elif angle_diff < -180:
                angle_diff += 360

            self._accumulated_rotation += abs(angle_diff)
            if self._accumulated_rotation >= 360:
                self.reps += 1
                self._accumulated_rotation %= 360

            self._prev_angle = current_angle

        return {
            "reps": self.reps,
            "rotation_progress": int(self._accumulated_rotation),
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0