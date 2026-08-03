# file_name: users.py

"""User profile endpoints.

Implements ``contracts/users/01_GET_PROFILE.md`` and
``contracts/users/02_UPDATE_PROFILE.md``.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.core.dependencies import CurrentUser, get_body_profile_repository
from app.domain.entities.user import BodyProfile
from app.infrastructure.repositories.user_repository import SqlBodyProfileRepository
from app.schemas.dto import BodyProfileResponse, UpdateProfileRequest
from app.schemas.response import success
from app.shared.exceptions import ProfileNotFoundError

router = APIRouter()

ProfileRepositoryDep = Annotated[
    SqlBodyProfileRepository, Depends(get_body_profile_repository)
]


def to_profile_response(profile: BodyProfile) -> BodyProfileResponse:
    """Shape a body profile for the API."""
    return BodyProfileResponse(
        id=str(profile.id),
        age=profile.age,
        gender=str(profile.gender),
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        fitness_goal=str(profile.fitness_goal),
        fitness_level=str(profile.fitness_level),
        problem_areas=list(profile.problem_areas),
        workout_duration_minutes=profile.workout_duration_minutes,
        body_type=profile.body_type,
        bmi=profile.bmi,
    )


@router.get(
    "/profile",
    status_code=status.HTTP_200_OK,
    summary="Get the authenticated user's body profile",
)
async def get_profile(
    user: CurrentUser, profiles: ProfileRepositoryDep
) -> dict[str, Any]:
    """Return the signed-in user's body profile.

    Raises:
        ProfileNotFoundError: If the user has not created one yet.
    """
    profile = await profiles.get_for_user(user.id)
    if profile is None:
        raise ProfileNotFoundError()

    return success(
        "Profile retrieved successfully.",
        to_profile_response(profile).model_dump(by_alias=True),
    )


@router.put(
    "/profile",
    status_code=status.HTTP_200_OK,
    summary="Create or replace the authenticated user's body profile",
)
async def update_profile(
    payload: UpdateProfileRequest,
    user: CurrentUser,
    profiles: ProfileRepositoryDep,
) -> dict[str, Any]:
    """Create the profile if absent, otherwise replace it.

    A user owns exactly one body profile, so this is idempotent by design.
    """
    existing = await profiles.get_for_user(user.id)

    # Rebuilt rather than mutated: a dataclass performs no validation on
    # assignment, so constructing the entity re-runs its invariants and enum
    # coercion against the submitted values.
    fields = {
        "user_id": user.id,
        "age": payload.age,
        "gender": payload.gender,
        "height_cm": payload.height_cm,
        "weight_kg": payload.weight_kg,
        "fitness_goal": payload.fitness_goal,
        "fitness_level": payload.fitness_level,
        "problem_areas": tuple(payload.problem_areas),
        "workout_duration_minutes": payload.workout_duration_minutes,
        "body_type": payload.body_type,
    }

    if existing is None:
        stored = await profiles.add(BodyProfile(**fields))
        message = "Profile created successfully."
    else:
        replacement = BodyProfile(
            id=existing.id, created_at=existing.created_at, **fields
        )
        stored = await profiles.update(replacement)
        message = "Profile updated successfully."

    return success(message, to_profile_response(stored).model_dump(by_alias=True))
