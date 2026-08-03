# file_name: models.py

"""Database models.

These tables implement the entities in ``docs/04_backend/29_DOMAIN_MODEL.md``.
They stay inside the persistence layer: ``26_PERSISTENCE_LAYER.md`` section 9
keeps database models internal, and section 14 forbids sharing them across
layers. Repositories translate them into domain entities.

Indexes follow ``docs/07_database/39_INDEXING_STRATEGY.md``: foreign keys used
for lookups are indexed, as are the columns the API filters and sorts on.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.session import Base
from app.infrastructure.database.types import GUID, JSONColumn, StringList


class UserModel(Base):
    """A registered user."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    google_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    profile_picture: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="Registered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    body_profile: Mapped["BodyProfileModel | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    progress: Mapped["ProgressModel | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class BodyProfileModel(Base):
    """A user's physical profile."""

    __tablename__ = "body_profiles"

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(32))
    height_cm: Mapped[float] = mapped_column(Float)
    weight_kg: Mapped[float] = mapped_column(Float)
    fitness_goal: Mapped[str] = mapped_column(String(32))
    fitness_level: Mapped[str] = mapped_column(String(32))
    problem_areas: Mapped[tuple[str, ...]] = mapped_column(StringList, default=list)
    workout_duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    body_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[UserModel] = relationship(back_populates="body_profile")


class ExerciseModel(Base):
    """Static exercise metadata, seeded from configuration."""

    __tablename__ = "exercises"

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(32), index=True)
    difficulty: Mapped[str] = mapped_column(String(32), index=True)
    exercise_type: Mapped[str] = mapped_column(String(32))
    movement_type: Mapped[str] = mapped_column(String(32))
    equipment: Mapped[tuple[str, ...]] = mapped_column(StringList, default=list)
    primary_muscles: Mapped[tuple[str, ...]] = mapped_column(StringList, default=list)
    secondary_muscles: Mapped[tuple[str, ...]] = mapped_column(StringList, default=list)
    instructions: Mapped[tuple[str, ...]] = mapped_column(StringList, default=list)
    is_supported: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExerciseSessionModel(Base):
    """One live exercise performed by a user."""

    __tablename__ = "exercise_sessions"
    __table_args__ = (
        Index("ix_exercise_sessions_user_status", "user_id", "status"),
        Index("ix_exercise_sessions_user_started", "user_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("exercises.id"))
    status: Mapped[str] = mapped_column(String(32), default="Created")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    total_reps: Mapped[int] = mapped_column(Integer, default=0)
    average_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)

    results: Mapped[list["ExerciseResultModel"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ExerciseResultModel(Base):
    """Detector output captured during an exercise session."""

    __tablename__ = "exercise_results"

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    exercise_session_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("exercise_sessions.id", ondelete="CASCADE"), index=True
    )
    frame_timestamp: Mapped[float] = mapped_column(Float)
    current_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rep_count: Mapped[int] = mapped_column(Integer, default=0)
    feedback: Mapped[tuple[str, ...]] = mapped_column(StringList, default=list)
    metrics: Mapped[dict] = mapped_column(JSONColumn, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    session: Mapped[ExerciseSessionModel] = relationship(back_populates="results")


class WorkoutPlanModel(Base):
    """A generated workout plan."""

    __tablename__ = "workout_plans"
    __table_args__ = (
        Index("ix_workout_plans_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(128))
    goal: Mapped[str] = mapped_column(String(32))
    difficulty: Mapped[str] = mapped_column(String(32))
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="Generated", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    exercises: Mapped[list["WorkoutExerciseModel"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )


class WorkoutExerciseModel(Base):
    """One exercise prescribed inside a workout plan."""

    __tablename__ = "workout_exercises"
    __table_args__ = (
        UniqueConstraint("workout_plan_id", "display_order", name="uq_plan_order"),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    workout_plan_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("workout_plans.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("exercises.id"))
    display_order: Mapped[int] = mapped_column(Integer)
    sets: Mapped[int] = mapped_column(Integer)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    hold_seconds: Mapped[int] = mapped_column(Integer, default=0)
    rest_seconds: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped[WorkoutPlanModel] = relationship(back_populates="exercises")


class WorkoutSessionModel(Base):
    """One workout performed by a user."""

    __tablename__ = "workout_sessions"
    __table_args__ = (
        Index("ix_workout_sessions_user_status", "user_id", "status"),
        Index("ix_workout_sessions_user_started", "user_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    workout_plan_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("workout_plans.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(32), default="Created")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    calories_burned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)


class FoodModel(Base):
    """One food item, seeded from configuration."""

    __tablename__ = "foods"

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    carbohydrates_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    serving_size: Mapped[str] = mapped_column(String(64))
    meal_types: Mapped[tuple[str, ...]] = mapped_column(StringList, default=list)
    diet_tags: Mapped[tuple[str, ...]] = mapped_column(StringList, default=list)


class DietPlanModel(Base):
    """A generated daily nutrition plan."""

    __tablename__ = "diet_plans"
    __table_args__ = (Index("ix_diet_plans_user_status", "user_id", "status"),)

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    goal: Mapped[str] = mapped_column(String(32))
    diet_preference: Mapped[str] = mapped_column(String(32))
    estimated_calories: Mapped[int] = mapped_column(Integer)
    water_target_ml: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="Generated")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    meals: Mapped[list["MealModel"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )


class MealModel(Base):
    """One meal inside a diet plan."""

    __tablename__ = "meals"

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    diet_plan_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("diet_plans.id", ondelete="CASCADE"), index=True
    )
    meal_type: Mapped[str] = mapped_column(String(32))
    display_order: Mapped[int] = mapped_column(Integer)

    plan: Mapped[DietPlanModel] = relationship(back_populates="meals")
    items: Mapped[list["MealItemModel"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan", lazy="selectin"
    )


class MealItemModel(Base):
    """One food and its serving amount inside a meal.

    The documented domain model has no quantity on the meal to food
    relationship. A meal without portions is not a usable recommendation, so the
    join carries ``servings``. Recorded in ``29_DOMAIN_MODEL.md``.
    """

    __tablename__ = "meal_items"

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    meal_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("meals.id", ondelete="CASCADE"), index=True
    )
    food_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("foods.id"))
    servings: Mapped[float] = mapped_column(Float)

    meal: Mapped[MealModel] = relationship(back_populates="items")


class ProgressModel(Base):
    """Long-term training statistics for one user."""

    __tablename__ = "progress"

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    total_workouts: Mapped[int] = mapped_column(Integer, default=0)
    total_exercises: Mapped[int] = mapped_column(Integer, default=0)
    total_minutes: Mapped[int] = mapped_column(Integer, default=0)
    last_workout_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    user: Mapped[UserModel] = relationship(back_populates="progress")
