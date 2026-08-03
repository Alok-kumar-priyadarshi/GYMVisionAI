# file_name: workouts.py

"""Workout endpoints.

Implements ``contracts/workouts/01_GENERATE_WORKOUT.md`` through
``contracts/workouts/05_DELETE_WORKOUT.md``.

Generation is deterministic and never uses AI, per
``docs/03_business/20_WORKOUT_ENGINE.md`` section 3.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.dependencies import (
    CurrentUser,
    get_body_profile_repository,
    get_exercise_repository,
    get_workout_plan_repository,
)
from app.domain.entities.user import BodyProfile
from app.domain.entities.workout import WorkoutExercise, WorkoutPlan
from app.domain.value_objects.identifier import new_id
from app.engines.workout import WorkoutProfile, build_workout_generator
from app.infrastructure.repositories.exercise_repository import SqlExerciseRepository
from app.infrastructure.repositories.user_repository import SqlBodyProfileRepository
from app.infrastructure.repositories.workout_repository import SqlWorkoutPlanRepository
from app.schemas.dto import (
    WorkoutDetailResponse,
    WorkoutExerciseResponse,
    WorkoutSummaryResponse,
)
from app.schemas.response import success
from app.shared.exceptions import (
    ProfileNotFoundError,
    WorkoutGenerationError,
    WorkoutNotFoundError,
)

router = APIRouter()

PlanRepositoryDep = Annotated[
    SqlWorkoutPlanRepository, Depends(get_workout_plan_repository)
]
ProfileRepositoryDep = Annotated[
    SqlBodyProfileRepository, Depends(get_body_profile_repository)
]
ExerciseRepositoryDep = Annotated[
    SqlExerciseRepository, Depends(get_exercise_repository)
]


def to_workout_profile(profile: BodyProfile) -> WorkoutProfile:
    """Project a stored body profile onto the engine's input contract."""
    return WorkoutProfile(
        age=profile.age,
        gender=profile.gender,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        goal=profile.fitness_goal,
        fitness_level=profile.fitness_level,
        available_minutes=profile.workout_duration_minutes,
    )


def to_summary(plan: WorkoutPlan) -> WorkoutSummaryResponse:
    """Shape a plan for a listing."""
    return WorkoutSummaryResponse(
        workout_id=str(plan.id),
        name=plan.title,
        difficulty=str(plan.difficulty),
        goal=str(plan.goal),
        estimated_duration_minutes=plan.estimated_duration_minutes,
        exercise_count=plan.exercise_count,
        created_at=plan.created_at,
    )


async def to_detail(
    plan: WorkoutPlan, exercises: SqlExerciseRepository
) -> WorkoutDetailResponse:
    """Shape a plan and resolve the exercises it references."""
    items = []
    for prescribed in plan.in_order():
        exercise = await exercises.get(prescribed.exercise_id)
        items.append(
            WorkoutExerciseResponse(
                exercise_id=str(prescribed.exercise_id),
                slug=exercise.slug if exercise else "",
                name=exercise.name if exercise else "",
                display_order=prescribed.display_order,
                sets=prescribed.sets,
                repetitions=prescribed.repetitions,
                hold_seconds=prescribed.hold_seconds,
                rest_seconds=prescribed.rest_seconds,
            )
        )

    return WorkoutDetailResponse(
        **to_summary(plan).model_dump(), exercises=items
    )


def _is_the_same_plan(existing: WorkoutPlan, generated) -> bool:
    """Report whether a generated plan matches one the user already has.

    Compared on what the user would actually see: the exercises, in order, with
    their prescriptions. Identifiers and timestamps necessarily differ and say
    nothing about whether the plan is different.
    """
    if existing.title != generated.name:
        return False
    if len(existing.exercises) != len(generated.exercises):
        return False

    return [
        (
            item.display_order,
            item.sets,
            item.repetitions,
            item.hold_seconds,
            item.rest_seconds,
        )
        for item in existing.in_order()
    ] == [
        (
            item.display_order,
            item.sets,
            item.repetitions,
            item.hold_seconds,
            item.rest_seconds,
        )
        for item in sorted(generated.exercises, key=lambda x: x.display_order)
    ]


@router.post(
    "/generate",
    summary="Generate a personalised workout",
)
async def generate_workout(
    response: Response,
    user: CurrentUser,
    profiles: ProfileRepositoryDep,
    plans: PlanRepositoryDep,
    exercises: ExerciseRepositoryDep,
) -> dict[str, Any]:
    """Generate and persist a workout from the user's profile.

    Raises:
        ProfileNotFoundError: If the user has no body profile.
        WorkoutGenerationError: If no plan can be produced.
    """
    profile = await profiles.get_for_user(user.id)
    if profile is None:
        raise ProfileNotFoundError()

    # A migrated but unseeded database would otherwise fail per-exercise, which
    # names a slug and says nothing about the actual cause.
    if not await exercises.list_supported():
        raise WorkoutGenerationError(
            "The exercise library is empty. Run 'python -m app.cli seed' to "
            "load it from configuration."
        )

    generated = build_workout_generator().generate(to_workout_profile(profile))

    # Generation is deterministic, so an unchanged profile produces the plan the
    # user already has. Storing it again would fill their history with
    # duplicates while the screen appeared not to react at all.
    current = await plans.get_current_for_user(user.id)
    if current is not None and _is_the_same_plan(current, generated):
        response.status_code = status.HTTP_200_OK
        summary = to_summary(current)
        summary.unchanged = True
        return success(
            "Your workout already matches your profile, so it is unchanged. "
            "Update your goal, fitness level or available time to get a "
            "different plan.",
            summary.model_dump(by_alias=True),
        )

    response.status_code = status.HTTP_201_CREATED

    # The engine works in slugs; the database works in identifiers. The plan's
    # identifier is minted first so its exercises can reference it.
    plan_id = new_id()
    prescriptions = []

    for item in generated.exercises:
        exercise = await exercises.get_by_slug(item.slug)
        if exercise is None:
            raise WorkoutGenerationError(
                f"Exercise '{item.slug}' is missing from the library."
            )
        prescriptions.append(
            WorkoutExercise(
                workout_plan_id=plan_id,
                exercise_id=exercise.id,
                display_order=item.display_order,
                sets=item.sets,
                repetitions=item.repetitions,
                hold_seconds=item.hold_seconds,
                rest_seconds=item.rest_seconds,
            )
        )

    stored = await plans.add(
        WorkoutPlan(
            id=plan_id,
            user_id=user.id,
            title=generated.name,
            goal=generated.goal,
            difficulty=generated.difficulty,
            estimated_duration_minutes=generated.estimated_duration_minutes,
            exercises=tuple(prescriptions),
        )
    )

    return success(
        "Workout generated successfully.",
        to_summary(stored).model_dump(by_alias=True),
    )


@router.get("/current", summary="Get the user's current workout")
async def get_current_workout(
    user: CurrentUser, plans: PlanRepositoryDep, exercises: ExerciseRepositoryDep
) -> dict[str, Any]:
    """Return the most recent unarchived workout.

    Raises:
        WorkoutNotFoundError: If the user has generated none.
    """
    plan = await plans.get_current_for_user(user.id)
    if plan is None:
        raise WorkoutNotFoundError("No current workout.")

    detail = await to_detail(plan, exercises)
    return success(
        "Current workout retrieved successfully.", detail.model_dump(by_alias=True)
    )


@router.get("/history", summary="List the user's workouts")
async def get_workout_history(
    user: CurrentUser,
    plans: PlanRepositoryDep,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    """Return the user's workouts, newest first."""
    offset = (page - 1) * limit
    stored = await plans.list_for_user(user.id, limit=limit, offset=offset)
    total = await plans.count_for_user(user.id)

    payload = success(
        "Workout history retrieved successfully.",
        [to_summary(plan).model_dump(by_alias=True) for plan in stored],
    )
    payload["pagination"] = {
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit if limit else 0,
    }
    return payload


@router.get("/{workout_id}", summary="Get one workout")
async def get_workout(
    workout_id: UUID,
    user: CurrentUser,
    plans: PlanRepositoryDep,
    exercises: ExerciseRepositoryDep,
) -> dict[str, Any]:
    """Return one of the user's workouts.

    Raises:
        WorkoutNotFoundError: If it does not exist or belongs to someone else.
    """
    plan = await plans.get(workout_id)
    if plan is None or plan.user_id != user.id:
        raise WorkoutNotFoundError()

    detail = await to_detail(plan, exercises)
    return success("Workout retrieved successfully.", detail.model_dump(by_alias=True))


@router.delete("/{workout_id}", summary="Delete one workout")
async def delete_workout(
    workout_id: UUID, user: CurrentUser, plans: PlanRepositoryDep
) -> dict[str, Any]:
    """Delete one of the user's workouts.

    Raises:
        WorkoutNotFoundError: If it does not exist or belongs to someone else.
    """
    plan = await plans.get(workout_id)
    if plan is None or plan.user_id != user.id:
        raise WorkoutNotFoundError()

    await plans.delete(workout_id)
    return success("Workout deleted successfully.", None)
