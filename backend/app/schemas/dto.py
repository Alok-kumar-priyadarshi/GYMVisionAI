# file_name: dto.py

"""Request and response DTOs.

``instructions/02_BACKEND_RULES.md`` section 9 requires every endpoint to use
DTOs and forbids returning ORM models directly.

``contracts/common/02_RESPONSE_FORMAT.md`` section 12 requires camelCase field
names and ISO-8601 timestamps, so these models serialise with camelCase aliases
while the Python attributes stay snake_case.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.value_objects.enums import DietPreference


def to_camel(value: str) -> str:
    """Convert a snake_case field name into camelCase."""
    head, *tail = value.split("_")
    return head + "".join(word.capitalize() for word in tail)


class ApiModel(BaseModel):
    """Base DTO serialising to camelCase."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class GoogleLoginRequest(ApiModel):
    """Body of ``POST /api/v1/auth/google``."""

    id_token: str = Field(min_length=1)


class RefreshTokenRequest(ApiModel):
    """Body of ``POST /api/v1/auth/refresh``."""

    refresh_token: str = Field(min_length=1)


class UserResponse(ApiModel):
    """A user, as returned by the authentication and user endpoints."""

    id: str
    name: str
    email: str
    picture: str | None = None
    created_at: datetime
    updated_at: datetime


class LoginResponse(ApiModel):
    """Tokens and the signed-in user."""

    access_token: str
    refresh_token: str
    expires_in: int
    user: UserResponse


class AccessTokenResponse(ApiModel):
    """A renewed access token."""

    access_token: str
    expires_in: int


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class BodyProfileResponse(ApiModel):
    """A user's physical profile."""

    id: str
    age: int
    gender: str
    height_cm: float
    weight_kg: float
    fitness_goal: str
    fitness_level: str
    problem_areas: list[str]
    workout_duration_minutes: int
    body_type: str | None = None
    bmi: float


class UpdateProfileRequest(ApiModel):
    """Body of ``PUT /api/v1/users/profile``."""

    age: int = Field(ge=13, le=100)
    gender: str
    height_cm: float = Field(gt=50, le=260)
    weight_kg: float = Field(gt=20, le=400)
    fitness_goal: str
    fitness_level: str
    problem_areas: list[str] = Field(default_factory=list)
    workout_duration_minutes: int = Field(default=30, ge=5, le=180)
    body_type: str | None = None


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------


class ExerciseSummaryResponse(ApiModel):
    """One exercise in the library listing."""

    exercise_id: str
    name: str
    category: str
    difficulty: str
    exercise_type: str
    detector_available: bool


class ExerciseDetailResponse(ExerciseSummaryResponse):
    """Full metadata for one exercise."""

    equipment: list[str]
    primary_muscles: list[str]
    secondary_muscles: list[str]
    instructions: list[str]
    movement_type: str


class StartSessionRequest(ApiModel):
    """Body of ``POST /api/v1/exercises/start``."""

    workout_id: str | None = None
    exercise_id: str = Field(min_length=1)


class SessionResponse(ApiModel):
    """An exercise session."""

    session_id: str
    workout_id: str | None
    exercise_id: str
    exercise_name: str
    status: str
    started_at: datetime


class LandmarkRequest(ApiModel):
    """One MediaPipe pose landmark."""

    x: float
    y: float
    z: float = 0.0
    visibility: float = 0.0


class ProcessFrameRequest(ApiModel):
    """Body of ``POST /api/v1/exercises/frame``."""

    session_id: str = Field(min_length=1)
    landmarks: list[LandmarkRequest] = Field(min_length=1)


class FrameResponse(ApiModel):
    """The analysis of one camera frame."""

    session_id: str
    exercise_id: str
    reps: int
    stage: str | None
    feedback: list[str]
    metrics: dict[str, Any]


class EndSessionRequest(ApiModel):
    """Body of ``POST /api/v1/exercises/end``."""

    session_id: str = Field(min_length=1)


class SessionSummaryResponse(ApiModel):
    """A finished exercise session."""

    session_id: str
    exercise_id: str
    status: str
    total_reps: int
    duration_seconds: int
    average_accuracy: float | None
    started_at: datetime
    completed_at: datetime | None


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------


class WorkoutExerciseResponse(ApiModel):
    """One exercise inside a workout plan."""

    exercise_id: str
    slug: str
    name: str
    display_order: int
    sets: int
    repetitions: int
    hold_seconds: int
    rest_seconds: int


class WorkoutSummaryResponse(ApiModel):
    """A generated workout, without its exercises."""

    workout_id: str
    name: str
    difficulty: str
    goal: str
    estimated_duration_minutes: int
    exercise_count: int
    created_at: datetime
    unchanged: bool = False
    """True when generation produced the plan the user already had."""


class WorkoutDetailResponse(WorkoutSummaryResponse):
    """A workout and every exercise it prescribes."""

    exercises: list[WorkoutExerciseResponse]


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


class ProgressResponse(ApiModel):
    """A user's long-term statistics."""

    current_streak: int
    longest_streak: int
    total_workouts: int
    total_exercises: int
    total_minutes: int
    average_workout_minutes: float
    last_workout_date: str | None


class DashboardResponse(ApiModel):
    """The dashboard summary."""

    user: UserResponse
    progress: ProgressResponse
    current_workout: WorkoutSummaryResponse | None
    has_profile: bool


class StatisticsResponse(ApiModel):
    """Aggregated training statistics."""

    total_workouts: int
    total_exercises: int
    total_minutes: int
    average_workout_minutes: float
    completed_sessions: int
    total_reps: int


# ---------------------------------------------------------------------------
# AI assistant
# ---------------------------------------------------------------------------


class ChatRequest(ApiModel):
    """Body of ``POST /api/v1/ai/chat``."""

    conversation_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(ApiModel):
    """A conversational reply."""

    conversation_id: str
    response: str
    created_at: datetime


class ExplainExerciseRequest(ApiModel):
    """Body of ``POST /api/v1/ai/explain``."""

    exercise_id: str = Field(min_length=1, max_length=64)


class ExerciseExplanationResponse(ApiModel):
    """An explanation of one exercise."""

    exercise_id: str
    title: str
    explanation: str


class ReviewWorkoutRequest(ApiModel):
    """Body of ``POST /api/v1/ai/review``."""

    workout_id: str = Field(min_length=1, max_length=64)


class WorkoutReviewResponse(ApiModel):
    """Coaching feedback on a completed workout."""

    workout_id: str
    summary: str
    strengths: list[str]
    improvements: list[str]
    motivation: str


# ---------------------------------------------------------------------------
# Diet
# ---------------------------------------------------------------------------


class GenerateDietRequest(ApiModel):
    """Body of ``POST /api/v1/diet/generate``. Every field is optional."""

    diet_preference: DietPreference | None = None


class MealItemResponse(ApiModel):
    """One food and how much of it to eat.

    The nutrition figures are for the portion as served, not per serving, so the
    client never has to multiply anything to display a meal.
    """

    food_id: str
    slug: str
    name: str
    category: str
    servings: float
    serving_size: str
    calories: float
    protein_g: float
    carbohydrates_g: float
    fat_g: float


class MealResponse(ApiModel):
    """One meal of the day."""

    meal_id: str
    meal_type: str
    display_order: int
    name: str
    target_calories: int
    items: list[MealItemResponse]


class DietTotalsResponse(ApiModel):
    """What the whole plan adds up to."""

    calories: float
    protein_g: float
    carbohydrates_g: float
    fat_g: float


class DietPlanSummaryResponse(ApiModel):
    """A stored plan, without its meals. Used by ``DIET-003``."""

    diet_plan_id: str
    goal: str
    diet_preference: str
    estimated_calories: int
    water_target_ml: int
    status: str
    meal_count: int
    created_at: datetime


class DietPlanResponse(DietPlanSummaryResponse):
    """A stored plan and everything in it. Used by ``DIET-001/002/004``."""

    meals: list[MealResponse]
    totals: DietTotalsResponse
