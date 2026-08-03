# file_name: butt_kicks_detector.py

import math
from app.engines.exercise.base_exercise import BaseExercise


class ButtKicksDetector(BaseExercise):
    # Thresholds for tracking butt kicks mechanics (knee flexion angle)
    UP_THRESHOLD = 60        # Heel pulled close to glutes angle threshold
    DOWN_THRESHOLD = 140     # Leg extended / resting angle threshold
    MIN_VISIBILITY = 0.7
    
    # Form check thresholds
    LEAN_THRESHOLD = 20      # Max torso forward lean allowed before flagging

    # Landmark Indices (MediaPipe Pose)
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    def __init__(self):
        super().__init__()
        self._current_active_leg = None

    def reset(self) -> None:
        self.reps = 0
        self.stage = "down"
        self._current_active_leg = None

    def process(self, landmarks) -> dict:
        # Check overall visibility for hips, knees, and ankles
        key_landmarks_visible = (
            landmarks[self.LEFT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_HIP].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_KNEE].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_KNEE].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_ANKLE].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_ANKLE].visibility > self.MIN_VISIBILITY
        )

        # Calculate knee angles (Hip -> Knee -> Ankle) for both legs
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
            # Determine active leg based on which knee is bent sharper (smaller angle)
            if left_knee_angle < right_knee_angle:
                active_angle = left_knee_angle
                active_leg = "left"
            else:
                active_angle = right_knee_angle
                active_leg = "right"

            # Rep counting logic for alternating butt kicks (heel pulls backward/upward)
            if active_angle < self.UP_THRESHOLD:
                if self.stage == "down" or self._current_active_leg != active_leg:
                    self.stage = "up"
                    self._current_active_leg = active_leg

            if active_angle > self.DOWN_THRESHOLD and self.stage == "up":
                self.stage = "down"
                self.reps += 1

        # Form Feedback: Check torso lean from vertical (Shoulder midpoint to Hip midpoint)
        shoulder_mid_x = (landmarks[self.LEFT_SHOULDER].x + landmarks[self.RIGHT_SHOULDER].x) / 2
        shoulder_mid_y = (landmarks[self.LEFT_SHOULDER].y + landmarks[self.RIGHT_SHOULDER].y) / 2
        hip_mid_x = (landmarks[self.LEFT_HIP].x + landmarks[self.RIGHT_HIP].x) / 2
        hip_mid_y = (landmarks[self.LEFT_HIP].y + landmarks[self.RIGHT_HIP].y) / 2

        dx = shoulder_mid_x - hip_mid_x
        dy = shoulder_mid_y - hip_mid_y
        torso_angle = self._safe_angle(dx, dy)

        if torso_angle <= self.LEAN_THRESHOLD:
            form_status = "GOOD POSTURE"
        else:
            form_status = "LEANING FORWARD"

        return {
            "reps": self.reps,
            "left_knee_angle": int(left_knee_angle),
            "right_knee_angle": int(right_knee_angle),
            "form_status": form_status,
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0