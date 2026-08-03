# file_name: progress.py

"""Progress domain entity.

``docs/04_backend/29_DOMAIN_MODEL.md`` section 8: progress is updated only after
a successful workout completion, and aggregates data from workout and exercise
sessions.

Streak rules are not specified anywhere, so this entity implements the ordinary
meaning of a daily streak: consecutive calendar days with at least one completed
workout. Two workouts on the same day do not extend a streak, and a missed day
resets it.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

from app.domain.value_objects.identifier import new_id


@dataclass
class Progress:
    """Long-term training statistics for one user."""

    user_id: UUID
    current_streak: int = 0
    longest_streak: int = 0
    total_workouts: int = 0
    total_exercises: int = 0
    total_minutes: int = 0
    last_workout_date: date | None = None
    id: UUID = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if min(
            self.current_streak,
            self.longest_streak,
            self.total_workouts,
            self.total_exercises,
            self.total_minutes,
        ) < 0:
            raise ValueError("progress totals cannot be negative")

    def record_workout(
        self,
        completed_on: date,
        exercises_completed: int,
        duration_minutes: int,
    ) -> None:
        """Record one completed workout.

        Args:
            completed_on: The calendar date the workout finished.
            exercises_completed: Exercises finished in that workout.
            duration_minutes: How long the workout took.

        Raises:
            ValueError: If a value is negative, or the date precedes the last
                recorded workout. Progress only moves forward.
        """
        if exercises_completed < 0 or duration_minutes < 0:
            raise ValueError("workout totals cannot be negative")
        if self.last_workout_date is not None and completed_on < self.last_workout_date:
            raise ValueError("a workout cannot be recorded before an earlier one")

        self._update_streak(completed_on)

        self.total_workouts += 1
        self.total_exercises += exercises_completed
        self.total_minutes += duration_minutes
        self.last_workout_date = completed_on

    def _update_streak(self, completed_on: date) -> None:
        """Extend, hold or reset the streak for a workout on a given date."""
        if self.last_workout_date is None:
            self.current_streak = 1
        elif completed_on == self.last_workout_date:
            # A second workout on the same day does not extend a daily streak.
            pass
        elif completed_on == self.last_workout_date + timedelta(days=1):
            self.current_streak += 1
        else:
            self.current_streak = 1

        self.longest_streak = max(self.longest_streak, self.current_streak)

    def break_streak_if_missed(self, today: date) -> None:
        """Reset the streak when a day has been missed.

        A streak decays with time rather than with activity, so it must be
        re-evaluated when the user is simply absent.
        """
        if self.last_workout_date is None:
            return
        if today - self.last_workout_date > timedelta(days=1):
            self.current_streak = 0

    @property
    def average_workout_minutes(self) -> float:
        """Return the mean workout length, or zero when nothing is recorded."""
        if self.total_workouts == 0:
            return 0.0
        return round(self.total_minutes / self.total_workouts, 1)
