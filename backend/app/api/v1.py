# file_name: v1.py

"""Version 1 API router.

``docs/04_backend/27_API_DESIGN_GUIDELINES.md`` section 2 versions every endpoint
under ``/api/v1``. Feature routers are registered here so the prefix and the set
of exposed endpoints live in one place.
"""

from fastapi import APIRouter

from app.api.routers import (
    ai,
    auth,
    diet,
    exercises,
    progress,
    users,
    workouts,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(exercises.router, prefix="/exercises", tags=["Exercises"])
api_router.include_router(workouts.router, prefix="/workouts", tags=["Workouts"])
api_router.include_router(progress.router, prefix="/progress", tags=["Progress"])
api_router.include_router(diet.router, prefix="/diet", tags=["Diet"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI Assistant"])
