# file_name: workout_generator.py

"""Deterministic workout plan generation.

Implements the pipeline in ``docs/03_business/20_WORKOUT_ENGINE.md`` section 8:

    User Profile -> Exercise Engine -> Filter -> Rank -> Generate -> WorkoutPlan

Generation never calls an AI provider and never reads the database. The same
profile always produces the same plan, which is the engine's primary success
criterion in section 20.
"""

import logging
import math
from typing import Iterable, Mapping

from app.engines.exercise.catalog.exercise_definition import (
    Difficulty,
    ExerciseCategory,
    ExerciseDefinition,
    ExerciseType,
    MovementType,
)
from app.engines.exercise.catalog.exercise_registry import (
    ExerciseRegistry,
    load_exercise_registry,
)
from app.engines.workout.template_loader import load_workout_templates
from app.engines.workout.workout_plan import (
    WorkoutExercise,
    WorkoutPhase,
    WorkoutPlan,
)
from app.engines.workout.workout_profile import (
    LEVEL_ORDER,
    FitnessGoal,
    WorkoutProfile,
)
from app.engines.workout.workout_template import LevelPrescription, WorkoutTemplate
from app.shared.exceptions import WorkoutGenerationError

logger = logging.getLogger(__name__)

DIFFICULTY_ORDER: dict[Difficulty, int] = {
    Difficulty.BEGINNER: 0,
    Difficulty.INTERMEDIATE: 1,
    Difficulty.ADVANCED: 2,
}
"""Ranking used to compare an exercise's difficulty against a user's level."""

TRIM_ORDER: tuple[WorkoutPhase, ...] = (
    WorkoutPhase.ISOLATION,
    WorkoutPhase.CORE,
    WorkoutPhase.COMPOUND,
)
"""Phases that may be trimmed, least essential first.

Warm-up is never trimmed and at least one compound exercise always remains.
Trimming takes from whichever of these phases currently has the most exercises,
using this order only to break ties, so a shortened session keeps its shape
instead of losing an entire phase.
"""

PHASE_MINIMUMS: dict[WorkoutPhase, int] = {
    WorkoutPhase.ISOLATION: 0,
    WorkoutPhase.CORE: 0,
    WorkoutPhase.COMPOUND: 1,
}
"""Exercises that must survive trimming in each trimmable phase."""


class WorkoutGenerator:
    """Builds workout plans from the exercise library and workout templates."""

    def __init__(
        self,
        registry: ExerciseRegistry,
        templates: Mapping[FitnessGoal, WorkoutTemplate],
    ) -> None:
        """Create a generator.

        Args:
            registry: The exercise library, the only source of exercises.
            templates: Generation rules keyed by fitness goal.
        """
        self._registry = registry
        self._templates = templates

    def generate(self, profile: WorkoutProfile) -> WorkoutPlan:
        """Generate a workout plan for one user profile.

        Args:
            profile: The user's attributes and constraints.

        Returns:
            A complete, immutable workout plan.

        Raises:
            WorkoutGenerationError: If the exercise library is empty, no template
                exists for the goal, or no exercise matches the user's
                constraints. No partial plan is ever returned.
        """
        logger.info("Workout generation started.")

        template = self._template_for(profile.goal)
        prescription = self._prescription_for(template, profile)
        candidates = self._filter(template, profile)
        selected = self._select(candidates, template, prescription)
        exercises = self._prescribe(selected, prescription)
        exercises = self._fit_to_available_time(exercises, template, profile)

        if not exercises:
            raise WorkoutGenerationError(
                "No exercises match the requested workout constraints."
            )

        plan = WorkoutPlan(
            template_id=template.id,
            name=template.name,
            goal=profile.goal,
            difficulty=template.difficulty_for(profile.fitness_level),
            estimated_duration_minutes=self._estimate_minutes(exercises, template),
            exercises=self._number(exercises),
        )

        logger.info(
            "Workout generated: %d exercises, %d minutes.",
            plan.exercise_count,
            plan.estimated_duration_minutes,
        )
        return plan

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def _template_for(self, goal: FitnessGoal) -> WorkoutTemplate:
        """Return the template for a goal."""
        try:
            return self._templates[goal]
        except KeyError as error:
            logger.error("Workout generation failed: no template for the goal.")
            raise WorkoutGenerationError(
                f"No workout template is configured for goal '{goal}'."
            ) from error

    @staticmethod
    def _prescription_for(
        template: WorkoutTemplate, profile: WorkoutProfile
    ) -> LevelPrescription:
        """Return the session parameters for the user's fitness level."""
        try:
            return template.prescription(profile.fitness_level)
        except KeyError as error:
            logger.error("Workout generation failed: fitness level not described.")
            raise WorkoutGenerationError(
                f"Template '{template.id}' does not describe fitness level "
                f"'{profile.fitness_level}'."
            ) from error

    def _filter(
        self, template: WorkoutTemplate, profile: WorkoutProfile
    ) -> tuple[ExerciseDefinition, ...]:
        """Return the exercises a user is allowed to be prescribed.

        Applies the selection rules in section 9: difficulty must not exceed the
        user's level, and equipment must be available. Exercises needing
        equipment the user may not have are excluded, which also satisfies the
        home-only constraint in section 12.
        """
        library = self._registry.all()
        if not library:
            logger.error("Workout generation failed: exercise library is empty.")
            raise WorkoutGenerationError("The exercise library is empty.")

        candidates = tuple(
            definition
            for definition in library
            if DIFFICULTY_ORDER[definition.difficulty] <= profile.level_rank
            and (template.allow_equipment or not definition.requires_equipment)
        )

        if not candidates:
            logger.error("Workout generation failed: no exercises match the profile.")
            raise WorkoutGenerationError(
                "No exercises match the user's fitness level and equipment."
            )

        logger.debug("Filtered %d candidate exercises.", len(candidates))
        return candidates

    def _select(
        self,
        candidates: Iterable[ExerciseDefinition],
        template: WorkoutTemplate,
        prescription: LevelPrescription,
    ) -> tuple[tuple[WorkoutPhase, ExerciseDefinition], ...]:
        """Choose exercises for each phase, in session order.

        Every exercise belongs to exactly one phase, so a plan can never contain
        a duplicate exercise.
        """
        wanted = {
            WorkoutPhase.WARM_UP: prescription.warm_up_exercises,
            WorkoutPhase.COMPOUND: prescription.compound_exercises,
            WorkoutPhase.ISOLATION: prescription.isolation_exercises,
            WorkoutPhase.CORE: prescription.core_exercises,
        }

        pools: dict[WorkoutPhase, list[ExerciseDefinition]] = {
            phase: [] for phase in WorkoutPhase
        }
        for definition in candidates:
            pools[self._phase_of(definition)].append(definition)

        selected: list[tuple[WorkoutPhase, ExerciseDefinition]] = []
        for phase in WorkoutPhase:
            ranked = sorted(pools[phase], key=lambda item: self._rank(item, template))
            selected.extend((phase, definition) for definition in ranked[: wanted[phase]])
        return tuple(selected)

    @staticmethod
    def _phase_of(definition: ExerciseDefinition) -> WorkoutPhase:
        """Return the session phase an exercise belongs to."""
        if definition.category is ExerciseCategory.WARM_UP:
            return WorkoutPhase.WARM_UP
        if definition.category is ExerciseCategory.CORE:
            return WorkoutPhase.CORE
        if definition.movement_type is MovementType.COMPOUND:
            return WorkoutPhase.COMPOUND
        return WorkoutPhase.ISOLATION

    @staticmethod
    def _rank(
        definition: ExerciseDefinition, template: WorkoutTemplate
    ) -> tuple[int, int, str]:
        """Return the sort key that orders exercises within a phase.

        Exercises training a muscle the goal emphasises come first, then the most
        demanding exercise the user is allowed, then the exercise identifier so
        that ranking is always stable.
        """
        emphasised = any(
            muscle in template.muscle_emphasis for muscle in definition.muscles
        )
        return (
            0 if emphasised else 1,
            -DIFFICULTY_ORDER[definition.difficulty],
            definition.id,
        )

    @staticmethod
    def _prescribe(
        selected: Iterable[tuple[WorkoutPhase, ExerciseDefinition]],
        prescription: LevelPrescription,
    ) -> list[WorkoutExercise]:
        """Apply sets, repetitions, hold time and rest to the chosen exercises."""
        exercises = []
        for phase, definition in selected:
            is_hold = definition.exercise_type is ExerciseType.DURATION
            exercises.append(
                WorkoutExercise(
                    display_order=0,
                    phase=phase,
                    exercise_id=definition.id,
                    slug=definition.slug,
                    name=definition.name,
                    exercise_type=definition.exercise_type,
                    sets=prescription.sets,
                    repetitions=0 if is_hold else prescription.repetitions,
                    hold_seconds=prescription.hold_seconds if is_hold else 0,
                    rest_seconds=prescription.rest_seconds,
                )
            )
        return exercises

    # ------------------------------------------------------------------
    # Duration
    # ------------------------------------------------------------------

    def _fit_to_available_time(
        self,
        exercises: list[WorkoutExercise],
        template: WorkoutTemplate,
        profile: WorkoutProfile,
    ) -> list[WorkoutExercise]:
        """Trim the session until it fits the user's available time.

        Exercises are removed from the least essential phase first, taking the
        lowest ranked exercise of that phase. Warm-up is preserved and at least
        one compound exercise always remains, so a trimmed session is still a
        complete workout rather than a partial one.
        """
        remaining = list(exercises)

        while self._estimate_minutes(remaining, template) > profile.available_minutes:
            removable = self._next_to_remove(remaining)
            if removable is None:
                logger.warning(
                    "Minimum session exceeds the user's available time of %d minutes.",
                    profile.available_minutes,
                )
                break
            remaining.remove(removable)

        return remaining

    @staticmethod
    def _next_to_remove(exercises: list[WorkoutExercise]) -> WorkoutExercise | None:
        """Return the exercise to drop next, or ``None`` if nothing may be cut.

        The largest trimmable phase gives one up, so trimming spreads across the
        session rather than deleting a whole phase. Ties fall back to
        ``TRIM_ORDER``, and the lowest ranked exercise of that phase goes first.
        """
        candidates = []
        for priority, phase in enumerate(TRIM_ORDER):
            in_phase = [item for item in exercises if item.phase is phase]
            if len(in_phase) > PHASE_MINIMUMS[phase]:
                candidates.append((-len(in_phase), priority, in_phase[-1]))

        if not candidates:
            return None
        return min(candidates, key=lambda entry: entry[:2])[2]

    @staticmethod
    def _estimate_minutes(
        exercises: Iterable[WorkoutExercise], template: WorkoutTemplate
    ) -> int:
        """Estimate how long a session takes, rounded up to whole minutes.

        Working time is the hold duration for duration exercises and
        ``repetitions * seconds_per_repetition`` for repetition exercises. Rest
        is counted after every set.
        """
        seconds = 0
        for exercise in exercises:
            working = (
                exercise.hold_seconds
                if exercise.is_hold
                else exercise.repetitions * template.seconds_per_repetition
            )
            seconds += exercise.sets * (working + exercise.rest_seconds)
        return math.ceil(seconds / 60)

    @staticmethod
    def _number(exercises: Iterable[WorkoutExercise]) -> tuple[WorkoutExercise, ...]:
        """Assign 1-based display order in session sequence."""
        return tuple(
            WorkoutExercise(
                display_order=position,
                phase=exercise.phase,
                exercise_id=exercise.exercise_id,
                slug=exercise.slug,
                name=exercise.name,
                exercise_type=exercise.exercise_type,
                sets=exercise.sets,
                repetitions=exercise.repetitions,
                hold_seconds=exercise.hold_seconds,
                rest_seconds=exercise.rest_seconds,
            )
            for position, exercise in enumerate(exercises, start=1)
        )


def build_workout_generator() -> WorkoutGenerator:
    """Return a generator wired to the application's configuration."""
    return WorkoutGenerator(load_exercise_registry(), load_workout_templates())
