# file_name: user.py

"""User domain entities.

Defined by ``docs/04_backend/29_DOMAIN_MODEL.md``. The domain layer is
framework-free: no FastAPI, no SQLAlchemy, no MediaPipe, no AI SDK, per
``docs/04_backend/28_BACKEND_ARCHITECTURE.md`` section 10.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from app.domain.value_objects.enums import (
    FitnessGoal,
    FitnessLevel,
    Gender,
    UserStatus,
)
from app.domain.value_objects.coercion import as_enum
from app.domain.value_objects.identifier import new_id


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC value."""
    return datetime.now(timezone.utc)


@dataclass
class User:
    """An authenticated GymVision AI user.

    Every user authenticates through Google OAuth, so there is no password and
    ``google_id`` is the external identity.
    """

    google_id: str
    email: str
    full_name: str
    profile_picture: str | None = None
    status: UserStatus = UserStatus.REGISTERED
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.google_id.strip():
            raise ValueError("a user requires a Google identifier")
        if "@" not in self.email:
            raise ValueError("a user requires a valid email address")
        self.status = as_enum(self.status, UserStatus)

    def activate(self) -> None:
        """Mark the user active, which happens once a profile exists."""
        self.status = UserStatus.ACTIVE
        self.touch()

    def deactivate(self) -> None:
        """Mark the user inactive without deleting their history."""
        self.status = UserStatus.INACTIVE
        self.touch()

    def touch(self) -> None:
        """Record that the entity changed."""
        self.updated_at = utc_now()


@dataclass
class BodyProfile:
    """A user's physical profile and training preferences.

    Owned by exactly one user. The Workout and Diet engines read a projection of
    this entity rather than the entity itself, so business rules stay in the
    engines and persistence stays here.
    """

    user_id: UUID
    age: int
    gender: Gender
    height_cm: float
    weight_kg: float
    fitness_goal: FitnessGoal
    fitness_level: FitnessLevel
    problem_areas: tuple[str, ...] = ()
    workout_duration_minutes: int = 30
    body_type: str | None = None
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not 13 <= self.age <= 100:
            raise ValueError("age must be between 13 and 100")
        if not 50 < self.height_cm <= 260:
            raise ValueError("height must be a plausible value in centimetres")
        if not 20 < self.weight_kg <= 400:
            raise ValueError("weight must be a plausible value in kilograms")
        if not 5 <= self.workout_duration_minutes <= 180:
            raise ValueError("workout duration must be between 5 and 180 minutes")

        self.gender = as_enum(self.gender, Gender)
        self.fitness_goal = as_enum(self.fitness_goal, FitnessGoal)
        self.fitness_level = as_enum(self.fitness_level, FitnessLevel)
        self.problem_areas = tuple(self.problem_areas)

    @property
    def bmi(self) -> float:
        """Return body mass index, rounded to one decimal place."""
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m * height_m), 1)

    def touch(self) -> None:
        """Record that the entity changed."""
        self.updated_at = utc_now()
