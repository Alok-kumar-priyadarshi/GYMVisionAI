# file_name: exercise_service.py

"""Exercise session use cases.

Coordinates the detector engine, the exercise catalogue and the repositories.
The detectors themselves stay stateless per frame, so the live rep count for an
active session is held here in memory and persisted on completion.

``contracts/exercises/02_PROCESS_FRAME.md`` section 12 forbids storing raw
frames or landmarks; only the detector's analysis is kept.
"""

import logging
import time
from dataclasses import dataclass, field, replace
from uuid import UUID

from app.domain.entities.exercise import Exercise, ExerciseResult, ExerciseSession
from app.domain.repositories.exercise_repository import (
    ExerciseRepository,
    ExerciseSessionRepository,
)
from app.engines.exercise.base_exercise import BaseExercise
from app.engines.exercise.detector_registry import DetectorRegistry
from app.engines.exercise.detector_result import DetectorResult
from app.engines.session.rep_validation import RepValidator
from app.shared.exceptions import (
    ExerciseNotFoundError,
    ExerciseSessionNotFoundError,
    InvalidSessionStateError,
    SessionAlreadyActiveError,
)

logger = logging.getLogger(__name__)

RESULT_SAMPLE_SECONDS = 1.0
"""How often a frame's analysis is persisted.

Frames arrive at up to 30 per second. Storing every one would write millions of
rows per workout for no analytical benefit, so results are sampled.
"""


MINIMUM_HOLD_SECONDS = 5
"""Shortest hold that counts as having done a duration exercise.

Opening the camera on a plank and closing it again is not a plank. Below this
the session is recorded as stopped rather than completed, so it neither ticks
the exercise off the workout nor inflates the progress totals.
"""


@dataclass
class LiveSession:
    """Runtime state for one active exercise session."""

    detector: BaseExercise
    exercise: Exercise
    started_at: float
    validator: RepValidator = field(default_factory=RepValidator)
    last_persisted_at: float = 0.0
    last_result: DetectorResult | None = None


class ExerciseService:
    """Runs live exercise sessions."""

    def __init__(
        self,
        exercises: ExerciseRepository,
        sessions: ExerciseSessionRepository,
        live_sessions: dict[UUID, LiveSession],
    ) -> None:
        self._exercises = exercises
        self._sessions = sessions
        self._live = live_sessions

    async def list_exercises(self) -> tuple[Exercise, ...]:
        """Return every supported exercise."""
        return await self._exercises.list_supported()

    async def get_exercise(self, slug: str) -> Exercise:
        """Return one exercise by slug.

        Raises:
            ExerciseNotFoundError: If no such exercise exists.
        """
        exercise = await self._exercises.get_by_slug(slug)
        if exercise is None:
            raise ExerciseNotFoundError(f"Exercise '{slug}' not found.")
        return exercise

    async def start(self, user_id: UUID, slug: str) -> tuple[ExerciseSession, Exercise]:
        """Start a live session for one exercise.

        Raises:
            ExerciseNotFoundError: If the exercise does not exist.
            SessionAlreadyActiveError: If the user already has one running.
            UnsupportedExerciseError: If no detector is registered.
            DetectorUnavailableError: If the detector cannot start.
        """
        exercise = await self.get_exercise(slug)

        if await self._sessions.get_active_for_user(user_id) is not None:
            raise SessionAlreadyActiveError()

        detector = DetectorRegistry.create(slug)

        session = ExerciseSession(user_id=user_id, exercise_id=exercise.id)
        session.start()
        stored = await self._sessions.add(session)

        self._live[stored.id] = LiveSession(
            detector=detector, exercise=exercise, started_at=time.monotonic()
        )
        logger.info("Exercise session started: %s", stored.id)
        return stored, exercise

    async def process_frame(
        self, user_id: UUID, session_id: UUID, landmarks
    ) -> tuple[DetectorResult, Exercise]:
        """Analyse one camera frame.

        Raises:
            ExerciseSessionNotFoundError: If the session does not exist or does
                not belong to the user.
            InvalidSessionStateError: If the session is no longer active.
            InvalidLandmarksError: If the frame carries no usable skeleton.
        """
        session = await self._require_own_session(user_id, session_id)

        if not session.is_active:
            raise InvalidSessionStateError("The exercise session has finished.")

        live = self._live.get(session_id)
        if live is None:
            # The process restarted, or the session began on another instance.
            raise InvalidSessionStateError(
                "The exercise session is no longer running on this server."
            )

        result = live.detector.analyze(landmarks)
        live.last_result = result

        elapsed = time.monotonic() - live.started_at

        # The detector's raw count is a claim, not a fact. Validation applies the
        # gates of `docs/02_runtime/16_REP_COUNTER_ENGINE.md` section 11 that do
        # not need the unbuilt FSM, which is what stops landmark noise near a
        # threshold from counting as dozens of repetitions.
        outcome = live.validator.observe(
            raw_reps=result.reps,
            confidence=result.confidence,
            elapsed_seconds=elapsed,
        )
        result = replace(result, reps=outcome.accepted_reps)

        session.record(total_reps=outcome.accepted_reps, duration_seconds=int(elapsed))
        await self._sessions.update(session)

        if elapsed - live.last_persisted_at >= RESULT_SAMPLE_SECONDS:
            live.last_persisted_at = elapsed
            await self._sessions.add_results(
                (
                    ExerciseResult(
                        exercise_session_id=session_id,
                        frame_timestamp=round(elapsed, 3),
                        current_stage=result.stage,
                        rep_count=result.reps,
                        feedback=result.feedback,
                        metrics=dict(result.metrics),
                        confidence=result.confidence,
                    ),
                )
            )

        return result, live.exercise

    async def end(self, user_id: UUID, session_id: UUID) -> ExerciseSession:
        """Finish a session and store its totals.

        Raises:
            ExerciseSessionNotFoundError: If the session does not exist or does
                not belong to the user.
            InvalidSessionStateError: If the session has already finished.
        """
        session = await self._require_own_session(user_id, session_id)

        if not session.is_active:
            raise InvalidSessionStateError("The exercise session has already finished.")

        live = self._live.pop(session_id, None)
        if live is not None:
            elapsed = int(time.monotonic() - live.started_at)
            # The validated count, never the detector's raw one: taking the
            # larger of the two would hand back exactly the inflated number
            # validation had just rejected.
            session.record(
                total_reps=max(session.total_reps, live.validator.accepted),
                duration_seconds=max(session.duration_seconds, elapsed),
            )

        accuracy = live.last_result.confidence if live and live.last_result else None

        if self._did_the_work(session, live.exercise if live else None):
            session.complete(average_accuracy=accuracy)
            logger.info("Exercise session completed: %s", session.id)
        else:
            # Ending a session having done nothing is stopping, not completing.
            # Recording it as completed would tick the exercise off the workout
            # and count towards the user's progress on the strength of no work.
            session.stop()
            logger.info("Exercise session stopped without work: %s", session.id)

        return await self._sessions.update(session)

    @staticmethod
    def _did_the_work(session: ExerciseSession, exercise: Exercise | None) -> bool:
        """Report whether a session recorded enough to count as done.

        A held exercise is measured in seconds and a counted one in repetitions,
        so the same session totals mean different things for each.
        """
        if exercise is not None and exercise.is_hold:
            return session.duration_seconds >= MINIMUM_HOLD_SECONDS
        return session.total_reps >= 1

    async def get_session(self, user_id: UUID, session_id: UUID) -> ExerciseSession:
        """Return one of the user's sessions."""
        return await self._require_own_session(user_id, session_id)

    async def history(
        self, user_id: UUID, limit: int, offset: int
    ) -> tuple[ExerciseSession, ...]:
        """Return the user's past sessions, newest first."""
        return await self._sessions.list_for_user(user_id, limit=limit, offset=offset)

    async def _require_own_session(
        self, user_id: UUID, session_id: UUID
    ) -> ExerciseSession:
        """Load a session and confirm it belongs to the caller.

        A session owned by someone else is reported as missing rather than
        forbidden, so the endpoint does not confirm that it exists.
        """
        session = await self._sessions.get(session_id)
        if session is None or session.user_id != user_id:
            raise ExerciseSessionNotFoundError()
        return session
