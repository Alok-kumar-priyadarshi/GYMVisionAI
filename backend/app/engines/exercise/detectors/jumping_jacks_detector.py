import math
from app.engines.exercise.base_exercise import BaseExercise


class JumpingJacksDetector(BaseExercise):
    # Thresholds for tracking jumping jacks mechanics
    UP_THRESHOLD = 35        # Arms high / legs wide angle threshold
    DOWN_THRESHOLD = 20      # Arms down / legs close angle threshold
    MIN_VISIBILITY = 0.7
    
    # Form check thresholds
    JUMP_HEIGHT_TOLERANCE = 0.02  # Minimal vertical hip movement required to count as a jump

    # Landmark Indices (MediaPipe Pose)
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_WRIST = 15
    RIGHT_WRIST = 16

    def __init__(self):
        super().__init__()
        self._hip_y_baseline = None

    def reset(self) -> None:
        self.reps = 0
        self.stage = None
        self._hip_y_baseline = None

    def process(self, landmarks) -> dict:
        # Check overall visibility for crucial upper and lower body parts
        key_landmarks_visible = (
            landmarks[self.LEFT_SHOULDER].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_SHOULDER].visibility > self.MIN_VISIBILITY and
            landmarks[self.LEFT_ANKLE].visibility > self.MIN_VISIBILITY and
            landmarks[self.RIGHT_ANKLE].visibility > self.MIN_VISIBILITY
        )

        # Calculate spread angles:
        # 1. Arm angle: angle between left wrist, left shoulder, and right shoulder (or vertical proxy)
        # To measure arm elevation, we track wrist-to-shoulder distance or body-to-arm angles. 
        # Here we use the span angle between Left Wrist -> Left Shoulder -> Right Shoulder.
        arm_spread_angle = self.calculate_angle(
            self.get_point(landmarks, self.LEFT_WRIST),
            self.get_point(landmarks, self.LEFT_SHOULDER),
            self.get_point(landmarks, self.RIGHT_SHOULDER)
        )

        # 2. Leg spread angle: Left Ankle -> Left Hip -> Right Ankle
        leg_spread_angle = self.calculate_angle(
            self.get_point(landmarks, self.LEFT_ANKLE),
            self.get_point(landmarks, self.LEFT_HIP),
            self.get_point(landmarks, self.RIGHT_ANKLE)
        )

        if key_landmarks_visible:
            # Jumping Jack "UP" position (Arms overhead, legs jumped apart)
            if arm_spread_angle < self.UP_THRESHOLD and leg_spread_angle > 50:
                self.stage = "up"

            # Jumping Jack "DOWN" position (Arms by side, legs together)
            if arm_spread_angle > 70 and leg_spread_angle < self.DOWN_THRESHOLD and self.stage == "up":
                self.stage = "down"
                self.reps += 1

        # Form Feedback: Check if feet/ankles are moving symmetrically or tracking stance stability
        ankle_distance = abs(landmarks[self.LEFT_ANKLE].x - landmarks[self.RIGHT_ANKLE].x)
        shoulder_distance = abs(landmarks[self.LEFT_SHOULDER].x - landmarks[self.RIGHT_SHOULDER].x)

        if ankle_distance > shoulder_distance * 1.2:
            stance_status = "WIDE STANCE"
        else:
            stance_status = "NARROW STANCE"

        return {
            "reps": self.reps,
            "arm_spread_angle": int(arm_spread_angle),
            "leg_spread_angle": int(leg_spread_angle),
            "stance_status": stance_status,
            "stage": self.stage
        }

    def _safe_angle(self, dx, dy):
        return math.degrees(math.atan2(abs(dx), abs(dy))) if dy != 0 else 0.0