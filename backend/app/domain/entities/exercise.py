# file_name: exercise.py

"""Exercise domain entities.

``docs/04_backend/29_DOMAIN_MODEL.md`` separates an exercise into static
metadata and runtime execution:

``Exercise``
    Metadata only. Read-only at runtime. Detector implementations are not
    domain entities and never appear here.

``ExerciseSession``
    One live execution of an exercise. Mutable only while active.

``ExerciseResult``
    Detector output captured during a session. Immutable after creation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import UUID

from app.domain.entities.user import utc_now
from app.domain.value_objects.enums import (
    Difficulty,
    Equipment,
    ExerciseCategory,
    ExerciseType,
    MovementType,
    SessionStatus,
)
from app.domain.value_objects.coercion import as_enum, as_enums
from app.domain.value_objects.identifier import new_id


@dataclass(frozen=True)
class Exercise:
    """Metadata for one supported exercise.

    Frozen because section 8 makes exercise metadata read-only during runtime.
    The authoritative source is the exercise configuration; this entity is its
    persisted form.
    """

    slug: str
    name: str
    category: ExerciseCategory
    difficulty: Difficulty
    exercise_type: ExerciseType
    movement_type: MovementType
    equipment: tuple[Equipment, ...]
    primary_muscles: tuple[str, ...]
    secondary_muscles: tuple[str, ...] = ()
    instructions: tuple[str, ...] = ()
    is_supported: bool = True
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.slug.strip():
            raise ValueError("an exercise requires a slug")
        if not self.primary_muscles:
            raise ValueError("an exercise requires at least one primary muscle")

        # Frozen dataclass: bypass the field guard to normalise on creation.
        object.__setattr__(self, "category", as_enum(self.category, ExerciseCategory))
        object.__setattr__(self, "difficulty", as_enum(self.difficulty, Difficulty))
        object.__setattr__(
            self, "exercise_type", as_enum(self.exercise_type, ExerciseType)
        )
        object.__setattr__(
            self, "movement_type", as_enum(self.movement_type, MovementType)
        )
        object.__setattr__(self, "equipment", as_enums(self.equipment, Equipment))

    @property
    def is_hold(self) -> bool:
        """Report whether the exercise is measured by hold time."""
        return self.exercise_type is ExerciseType.DURATION


@dataclass
class ExerciseSession:
    """One live exercise performed by a user.

    Belongs to one user and references one exercise. Mutable only while active,
    per the business rules in section 8.
    """

    user_id: UUID
    exercise_id: UUID
    status: SessionStatus = SessionStatus.CREATED
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
    duration_seconds: int = 0
    total_reps: int = 0
    average_accuracy: float | None = None
    id: UUID = field(default_factory=new_id)

    @property
    def is_active(self) -> bool:
        """Report whether the session still accepts changes."""
        return self.status in (SessionStatus.CREATED, SessionStatus.RUNNING)

    def __post_init__(self) -> None:
        self.status = as_enum(self.status, SessionStatus)

    def start(self) -> None:
        """Move the session into the running state.

        Raises:
            ValueError: If the session has already finished.
        """
        self._require_active()
        self.status = SessionStatus.RUNNING

    def record(self, total_reps: int, duration_seconds: int) -> None:
        """Update the session's running totals.

        Raises:
            ValueError: If the session has already finished, or a total moves
                backwards.
        """
        self._require_active()
        if total_reps < self.total_reps:
            raise ValueError("repetition count cannot decrease")
        if duration_seconds < self.duration_seconds:
            raise ValueError("duration cannot decrease")

        self.total_reps = total_reps
        self.duration_seconds = duration_seconds

    def complete(self, average_accuracy: float | None = None) -> None:
        """Finish the session and lock it.

        Raises:
            ValueError: If the session has already finished, or the accuracy is
                outside 0.0 to 1.0.
        """
        self._require_active()
        if average_accuracy is not None and not 0.0 <= average_accuracy <= 1.0:
            raise ValueError("average accuracy must be between 0.0 and 1.0")

        self.status = SessionStatus.COMPLETED
        self.completed_at = utc_now()
        self.average_accuracy = average_accuracy

    def stop(self) -> None:
        """End the session early, preserving progress."""
        self._require_active()
        self.status = SessionStatus.STOPPED
        self.completed_at = utc_now()

    def _require_active(self) -> None:
        if not self.is_active:
            raise ValueError("the exercise session has already finished")


@dataclass(frozen=True)
class ExerciseResult:
    """Detector output captured during an exercise session.

    Frozen because section 8 makes exercise results immutable after storage.
    It records what the detector reported, never how the detector works.
    """

    exercise_session_id: UUID
    frame_timestamp: float
    rep_count: int
    current_stage: str | None = None
    feedback: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.rep_count < 0:
            raise ValueError("repetition count cannot be negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
