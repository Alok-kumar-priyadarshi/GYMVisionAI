# file_name: test_layer_boundaries.py

"""Architectural tests for the domain layer.

``docs/04_backend/28_BACKEND_ARCHITECTURE.md`` section 10 forbids the domain from
depending on FastAPI, SQLAlchemy, MediaPipe, the Groq SDK or OpenCV, and
section 12 requires dependencies to point inward. Those rules are only real if
something checks them.
"""

import ast
import inspect
from abc import ABC
from pathlib import Path

import pytest

from app.domain.repositories.diet_repository import DietPlanRepository, FoodRepository
from app.domain.repositories.exercise_repository import (
    ExerciseRepository,
    ExerciseSessionRepository,
)
from app.domain.repositories.progress_repository import ProgressRepository
from app.domain.repositories.user_repository import (
    BodyProfileRepository,
    UserRepository,
)
from app.domain.repositories.workout_repository import (
    WorkoutPlanRepository,
    WorkoutSessionRepository,
)

DOMAIN_ROOT = Path(__file__).resolve().parents[3] / "app" / "domain"

FORBIDDEN_PACKAGES = {
    "fastapi",
    "starlette",
    "sqlalchemy",
    "alembic",
    "mediapipe",
    "cv2",
    "groq",
    "pydantic",
    "pydantic_settings",
}

REPOSITORIES = [
    UserRepository,
    BodyProfileRepository,
    ExerciseRepository,
    ExerciseSessionRepository,
    WorkoutPlanRepository,
    WorkoutSessionRepository,
    FoodRepository,
    DietPlanRepository,
    ProgressRepository,
]


def domain_modules() -> list[Path]:
    return sorted(DOMAIN_ROOT.rglob("*.py"))


def imported_roots(path: Path) -> set[str]:
    """Return the top-level package of every import in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])

    return roots


def test_the_domain_layer_has_modules():
    assert domain_modules()


@pytest.mark.parametrize("path", domain_modules(), ids=lambda p: p.name)
def test_the_domain_imports_no_framework(path):
    forbidden = imported_roots(path) & FORBIDDEN_PACKAGES

    assert not forbidden, f"{path.name} imports {sorted(forbidden)}"


@pytest.mark.parametrize("path", domain_modules(), ids=lambda p: p.name)
def test_the_domain_depends_on_nothing_outside_itself(path):
    """The domain is the innermost ring: it may not import engines or the API."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    app_imports = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("app."):
                app_imports.add(node.module)

    outside = {
        module
        for module in app_imports
        if not module.startswith("app.domain")
    }
    assert not outside, f"{path.name} imports {sorted(outside)}"


@pytest.mark.parametrize("repository", REPOSITORIES, ids=lambda r: r.__name__)
def test_every_repository_is_an_interface(repository):
    assert issubclass(repository, ABC)
    assert getattr(repository, "__abstractmethods__", None)


@pytest.mark.parametrize("repository", REPOSITORIES, ids=lambda r: r.__name__)
def test_a_repository_cannot_be_instantiated(repository):
    with pytest.raises(TypeError):
        repository()


@pytest.mark.parametrize("repository", REPOSITORIES, ids=lambda r: r.__name__)
def test_every_repository_method_is_asynchronous(repository):
    for name in repository.__abstractmethods__:
        method = getattr(repository, name)
        assert inspect.iscoroutinefunction(method), f"{repository.__name__}.{name}"


@pytest.mark.parametrize("repository", REPOSITORIES, ids=lambda r: r.__name__)
def test_every_repository_method_is_documented(repository):
    for name in repository.__abstractmethods__:
        assert getattr(repository, name).__doc__, f"{repository.__name__}.{name}"


def test_every_aggregate_root_has_a_repository():
    # Aggregate roots per 29_DOMAIN_MODEL.md section 4.
    covered = {repository.__name__ for repository in REPOSITORIES}

    assert {
        "UserRepository",
        "ExerciseRepository",
        "ExerciseSessionRepository",
        "WorkoutPlanRepository",
        "WorkoutSessionRepository",
        "DietPlanRepository",
        "FoodRepository",
        "ProgressRepository",
    } <= covered
