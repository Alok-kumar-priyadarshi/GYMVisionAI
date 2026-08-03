# file_name: test_session_runtime.py

"""Integration tests for the runtime path from detector output to session state.

Covers the multi-exercise, pause-and-resume and interrupted scenarios required
by ``docs/02_runtime/18_WORKOUT_SESSION_ENGINE.md`` section 19, driving a session
with real generated plans and real detector output.
"""

import pytest

from app.engines.exercise.detector_registry import DetectorRegistry
from app.engines.session import (
    DetectorRepAdapter,
    WorkoutSession,
    WorkoutStatus,
)
from app.engines.workout import build_workout_generator
from app.engines.workout.workout_profile import WorkoutProfile
from tests.fixtures.landmarks import build_pose, push_up_pose
from tests.fixtures.session import (
    FakeClock,
    completed_rep,
    hold_exercise,
    plan,
    repetition_exercise,
)
from tests.fixtures.workout import PROFILE_DEFAULTS


@pytest.fixture(scope="module")
def generated_plan():
    generator = build_workout_generator()
    return generator.generate(WorkoutProfile(**PROFILE_DEFAULTS))


def test_a_generated_plan_can_drive_a_session(generated_plan):
    clock = FakeClock()
    session = WorkoutSession("wrk_1", generated_plan, clock=clock)

    state = session.start()

    assert state.status is WorkoutStatus.ACTIVE
    assert state.exercise_slug == generated_plan.exercises[0].slug
    assert state.remaining_exercises == generated_plan.exercise_count


def test_a_generated_plan_can_be_completed(generated_plan):
    clock = FakeClock()
    session = WorkoutSession("wrk_1", generated_plan, clock=clock)
    session.start()

    guard = 0
    while not session.is_finished and guard < 5000:
        guard += 1
        state = session.state()

        if state.status is WorkoutStatus.RESTING:
            clock.advance(state.rest_seconds_remaining or 1)
            session.refresh()
            continue

        if state.target_hold_seconds:
            session.record_hold(True)
            clock.advance(state.target_hold_seconds)
            session.refresh()
        else:
            session.record_rep(completed_rep(state.current_rep + 1))

    summary = session.summary()

    assert summary.status is WorkoutStatus.COMPLETED
    assert summary.completion_percentage == 100.0
    assert summary.exercises_completed == generated_plan.exercise_count
    assert summary.sets_completed == summary.sets_planned


def test_real_detector_output_drives_repetition_progress():
    detector = DetectorRegistry.create("push_ups")
    adapter = DetectorRepAdapter()
    session = WorkoutSession(
        "wrk_1",
        plan(repetition_exercise(sets=1, repetitions=2, rest_seconds=0)),
        clock=FakeClock(),
    )
    session.start()

    for _ in range(2):
        session.record_rep(adapter.observe(detector.analyze(push_up_pose(180))))
        session.record_rep(adapter.observe(detector.analyze(push_up_pose(60))))

    assert session.status is WorkoutStatus.COMPLETED
    assert session.summary().reps_completed == 2


def test_an_untracked_skeleton_makes_no_progress():
    detector = DetectorRegistry.create("push_ups")
    adapter = DetectorRepAdapter()
    session = WorkoutSession(
        "wrk_1", plan(repetition_exercise(repetitions=3)), clock=FakeClock()
    )
    session.start()

    for _ in range(10):
        session.record_rep(adapter.observe(detector.analyze(build_pose(visibility=0.1))))

    assert session.state().current_rep == 0


def test_a_held_exercise_is_timed_by_the_session():
    # The plank detector reports only that the position is held.
    detector = DetectorRegistry.create("plank")
    aligned = build_pose({11: (0.30, 0.50), 23: (0.50, 0.50), 27: (0.70, 0.50)})
    clock = FakeClock()
    session = WorkoutSession(
        "wrk_1",
        plan(hold_exercise(sets=1, hold_seconds=30, rest_seconds=0)),
        clock=clock,
    )
    session.start()

    result = detector.analyze(aligned)
    session.record_hold(DetectorRepAdapter.is_holding(result))
    clock.advance(30)

    assert session.refresh().status is WorkoutStatus.COMPLETED


def test_pausing_preserves_progress_across_a_long_interruption():
    clock = FakeClock()
    session = WorkoutSession(
        "wrk_1",
        plan(repetition_exercise(sets=2, repetitions=2, rest_seconds=0)),
        clock=clock,
    )
    session.start()
    session.record_rep(completed_rep(1))
    clock.advance(20)
    session.pause()

    clock.advance(3600)
    session.resume()

    state = session.state()
    assert state.current_rep == 1
    assert state.workout_seconds == 20
    assert state.status is WorkoutStatus.ACTIVE


def test_an_interrupted_session_reports_partial_progress(generated_plan):
    clock = FakeClock()
    session = WorkoutSession("wrk_1", generated_plan, clock=clock)
    session.start()
    session.record_rep(completed_rep(1))
    clock.advance(45)

    session.stop()
    summary = session.summary()

    assert summary.status is WorkoutStatus.STOPPED
    assert summary.completion_percentage < 100.0
    assert summary.workout_seconds == 45


def test_state_and_summary_serialise_to_plain_types(generated_plan):
    session = WorkoutSession("wrk_1", generated_plan, clock=FakeClock())
    session.start()

    state = session.state().to_dict()
    summary = session.summary().to_dict()

    assert isinstance(state["status"], str)
    assert isinstance(summary["achievements"], list)
