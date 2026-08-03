# file_name: test_workout_session.py

"""Unit tests for the workout session engine."""

import pytest

from app.engines.exercise.catalog.exercise_definition import Difficulty
from app.engines.session.runtime_contracts import WorkoutStatus
from app.engines.session.workout_session import WorkoutSession
from app.engines.workout.workout_plan import WorkoutPlan
from app.engines.workout.workout_profile import FitnessGoal
from app.shared.exceptions import InvalidSessionStateError, SessionNotActiveError
from tests.fixtures.session import (
    FakeClock,
    completed_rep,
    hold_exercise,
    partial_rep,
    plan,
    repetition_exercise,
)


def session(*exercises, clock: FakeClock | None = None) -> WorkoutSession:
    clock = clock or FakeClock()
    return WorkoutSession("wrk_1", plan(*exercises), clock=clock)


def complete_set(active: WorkoutSession, repetitions: int) -> None:
    """Report enough repetitions to finish one set."""
    for index in range(1, repetitions + 1):
        active.record_rep(completed_rep(index))


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_a_new_session_is_ready():
    assert session().state().status is WorkoutStatus.READY


def test_starting_activates_the_session():
    assert session().start().status is WorkoutStatus.ACTIVE


def test_a_session_cannot_start_twice():
    active = session()
    active.start()

    with pytest.raises(InvalidSessionStateError):
        active.start()


def test_a_plan_without_exercises_is_rejected():
    empty_plan = WorkoutPlan(
        template_id="WO-0001",
        name="Empty",
        goal=FitnessGoal.GENERAL_FITNESS,
        difficulty=Difficulty.BEGINNER,
        estimated_duration_minutes=0,
        exercises=(),
    )

    with pytest.raises(InvalidSessionStateError):
        WorkoutSession("wrk_1", empty_plan)


def test_pausing_and_resuming_returns_to_the_previous_state():
    active = session()
    active.start()

    assert active.pause().status is WorkoutStatus.PAUSED
    assert active.resume().status is WorkoutStatus.ACTIVE


def test_pausing_during_rest_resumes_into_rest():
    active = session(repetition_exercise(sets=2, repetitions=1))
    active.start()
    active.record_rep(completed_rep())

    assert active.state().status is WorkoutStatus.RESTING
    active.pause()

    assert active.resume().status is WorkoutStatus.RESTING


def test_a_session_that_has_not_started_cannot_pause():
    with pytest.raises(InvalidSessionStateError):
        session().pause()


def test_only_a_paused_session_can_resume():
    active = session()
    active.start()

    with pytest.raises(InvalidSessionStateError):
        active.resume()


def test_stopping_ends_the_session():
    active = session()
    active.start()

    assert active.stop().status is WorkoutStatus.STOPPED
    assert active.is_finished is True


def test_a_finished_session_cannot_stop_again():
    active = session()
    active.start()
    active.stop()

    with pytest.raises(InvalidSessionStateError):
        active.stop()


# ---------------------------------------------------------------------------
# Repetition progress
# ---------------------------------------------------------------------------


def test_completed_repetitions_are_counted():
    active = session(repetition_exercise(repetitions=3))
    active.start()

    state = active.record_rep(completed_rep(1))

    assert state.current_rep == 1


def test_incomplete_repetitions_are_not_counted():
    active = session(repetition_exercise(repetitions=3))
    active.start()

    assert active.record_rep(partial_rep()).current_rep == 0


def test_reaching_the_target_completes_the_set():
    active = session(repetition_exercise(sets=2, repetitions=2))
    active.start()

    complete_set(active, 2)
    state = active.state()

    assert state.current_set == 2
    assert state.current_rep == 0
    assert state.status is WorkoutStatus.RESTING


def test_finishing_every_set_moves_to_the_next_exercise():
    active = session(
        repetition_exercise(1, "push_ups", sets=1, repetitions=1),
        repetition_exercise(2, "bodyweight_squats", sets=1, repetitions=1),
    )
    active.start()
    active.record_rep(completed_rep())

    assert active.state().exercise_slug == "bodyweight_squats"


def test_finishing_every_exercise_completes_the_workout():
    active = session(repetition_exercise(sets=1, repetitions=1))
    active.start()

    state = active.record_rep(completed_rep())

    assert state.status is WorkoutStatus.COMPLETED
    assert state.completion_percentage == 100.0
    assert state.exercise_slug is None


def test_repetitions_are_ignored_while_resting():
    active = session(repetition_exercise(sets=2, repetitions=1))
    active.start()
    active.record_rep(completed_rep())

    state = active.record_rep(completed_rep())

    assert state.status is WorkoutStatus.RESTING
    assert state.current_rep == 0


def test_repetitions_are_ignored_while_paused():
    active = session(repetition_exercise(repetitions=3))
    active.start()
    active.pause()

    assert active.record_rep(completed_rep()).current_rep == 0


def test_repetitions_are_ignored_for_a_held_exercise():
    active = session(hold_exercise())
    active.start()

    assert active.record_rep(completed_rep()).current_rep == 0


def test_progress_before_starting_is_rejected():
    with pytest.raises(SessionNotActiveError):
        session().record_rep(completed_rep())


def test_progress_after_finishing_is_rejected():
    active = session(repetition_exercise(sets=1, repetitions=1))
    active.start()
    active.record_rep(completed_rep())

    with pytest.raises(SessionNotActiveError) as error:
        active.record_rep(completed_rep())

    assert error.value.error_code == "WORKOUT-004"
    assert error.value.http_status == 409


# ---------------------------------------------------------------------------
# Timers
# ---------------------------------------------------------------------------


def test_workout_time_accumulates_while_active():
    clock = FakeClock()
    active = session(clock=clock)
    active.start()

    clock.advance(12)

    assert active.refresh().workout_seconds == 12


def test_no_time_accumulates_before_starting():
    clock = FakeClock()
    active = session(clock=clock)

    clock.advance(60)

    assert active.start().workout_seconds == 0


def test_no_time_accumulates_while_paused():
    clock = FakeClock()
    active = session(clock=clock)
    active.start()
    clock.advance(10)
    active.pause()

    clock.advance(300)
    active.resume()

    assert active.refresh().workout_seconds == 10


def test_exercise_time_resets_between_exercises():
    clock = FakeClock()
    active = session(
        repetition_exercise(1, "push_ups", sets=1, repetitions=1, rest_seconds=0),
        repetition_exercise(2, "bodyweight_squats", sets=1, repetitions=1),
        clock=clock,
    )
    active.start()
    clock.advance(40)
    active.refresh()
    active.record_rep(completed_rep())

    assert active.state().exercise_seconds == 0
    assert active.state().workout_seconds == 40


def test_rest_ends_automatically_and_work_resumes():
    clock = FakeClock()
    active = session(
        repetition_exercise(sets=2, repetitions=1, rest_seconds=30), clock=clock
    )
    active.start()
    active.record_rep(completed_rep())

    clock.advance(30)

    assert active.refresh().status is WorkoutStatus.ACTIVE


def test_remaining_rest_counts_down():
    clock = FakeClock()
    active = session(
        repetition_exercise(sets=2, repetitions=1, rest_seconds=30), clock=clock
    )
    active.start()
    active.record_rep(completed_rep())

    clock.advance(10)

    assert active.refresh().rest_seconds_remaining == 20


def test_a_set_with_no_rest_returns_straight_to_work():
    active = session(repetition_exercise(sets=2, repetitions=1, rest_seconds=0))
    active.start()

    assert active.record_rep(completed_rep()).status is WorkoutStatus.ACTIVE


# ---------------------------------------------------------------------------
# Held exercises
# ---------------------------------------------------------------------------


def test_hold_time_accumulates_only_while_holding():
    clock = FakeClock()
    active = session(hold_exercise(hold_seconds=60), clock=clock)
    active.start()

    clock.advance(10)
    active.refresh()
    assert active.state().hold_seconds == 0

    active.record_hold(True)
    clock.advance(15)

    assert active.refresh().hold_seconds == 15


def test_releasing_the_hold_stops_the_timer():
    clock = FakeClock()
    active = session(hold_exercise(hold_seconds=60), clock=clock)
    active.start()
    active.record_hold(True)
    clock.advance(10)
    active.record_hold(False)

    clock.advance(30)

    assert active.refresh().hold_seconds == 10


def test_reaching_the_target_hold_completes_the_set():
    clock = FakeClock()
    active = session(hold_exercise(sets=1, hold_seconds=30), clock=clock)
    active.start()
    active.record_hold(True)

    clock.advance(30)

    assert active.refresh().status is WorkoutStatus.COMPLETED


def test_holds_are_ignored_for_a_counted_exercise():
    clock = FakeClock()
    active = session(repetition_exercise(), clock=clock)
    active.start()
    active.record_hold(True)

    clock.advance(60)

    assert active.refresh().hold_seconds == 0


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def test_state_reports_the_remaining_work():
    active = session(
        repetition_exercise(1, "push_ups", sets=3, repetitions=5),
        repetition_exercise(2, "bodyweight_squats", sets=2, repetitions=5),
    )
    active.start()

    state = active.state()

    assert state.total_sets == 3
    assert state.remaining_sets == 3
    assert state.remaining_exercises == 2
    assert state.target_reps == 5


def test_completion_percentage_tracks_completed_sets():
    active = session(repetition_exercise(sets=4, repetitions=1, rest_seconds=0))
    active.start()
    active.record_rep(completed_rep())

    assert active.state().completion_percentage == 25.0


def test_summary_reports_the_session_statistics():
    clock = FakeClock()
    active = session(
        repetition_exercise(sets=2, repetitions=2, rest_seconds=0), clock=clock
    )
    active.start()
    complete_set(active, 2)
    clock.advance(5)
    complete_set(active, 2)

    summary = active.summary()

    assert summary.status is WorkoutStatus.COMPLETED
    assert summary.exercises_completed == 1
    assert summary.sets_completed == 2
    assert summary.sets_planned == 2
    assert summary.reps_completed == 4
    assert summary.completion_percentage == 100.0


def test_a_stopped_session_preserves_its_progress():
    active = session(repetition_exercise(sets=4, repetitions=1, rest_seconds=0))
    active.start()
    active.record_rep(completed_rep())
    active.stop()

    summary = active.summary()

    assert summary.status is WorkoutStatus.STOPPED
    assert summary.sets_completed == 1
    assert summary.completion_percentage == 25.0


def test_unmeasurable_fields_are_reported_as_absent():
    # Calories, streaks and form scores need inputs that do not exist yet.
    active = session()
    active.start()

    assert active.state().calories is None
    assert active.state().current_streak is None
    assert active.summary().average_form_score is None
