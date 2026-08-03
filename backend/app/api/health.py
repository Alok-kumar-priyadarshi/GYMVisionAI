# file_name: health.py

"""Health, readiness and liveness endpoints.

``docs/11_monitoring/49_MONITORING_ARCHITECTURE.md`` section 8 requires every
service to expose ``/health``, ``/ready`` and ``/live``, verifying database
connectivity, configuration loading, AI provider availability as a non-blocking
check, and application readiness.

These routes sit outside ``/api/v1`` because they are consumed by the deployment
platform rather than by the product, and they are public: a platform probe
carries no credentials.
"""

import logging
from enum import StrEnum
from typing import Any

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.config import Settings, get_settings
from app.engines.exercise.catalog import load_exercise_registry
from app.engines.nutrition import load_food_registry
from app.engines.nutrition.diet_rules import load_cached_diet_rules
from app.engines.workout import load_workout_templates
from app.schemas.response import success

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
"""Injected rather than read directly, so an application built with explicit
settings reports those settings and not the process environment."""


class ComponentStatus(StrEnum):
    """Reported state of one checked component."""

    OK = "ok"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"


def _check_configuration(settings: Settings) -> dict[str, Any]:
    """Report whether configuration loaded and which secrets are absent.

    Secret names are reported, never their values, so an operator can see what a
    deployment is missing without exposing anything sensitive.
    """
    missing = settings.missing_secrets()
    return {
        "status": ComponentStatus.OK,
        "environment": str(settings.environment),
        "missing_secrets": list(missing),
    }


def _check_engines() -> dict[str, Any]:
    """Report whether the configuration-driven engines loaded.

    The registries are cached, so this re-reads nothing after startup.
    """
    try:
        exercises = len(load_exercise_registry())
        workouts = len(load_workout_templates())
        foods = len(load_food_registry())
        load_cached_diet_rules()
    except Exception as error:  # noqa: BLE001 - reported, never raised to a probe
        logger.exception("Engine health check failed.")
        return {"status": ComponentStatus.FAILED, "detail": type(error).__name__}

    return {
        "status": ComponentStatus.OK,
        "exercises": exercises,
        "workout_templates": workouts,
        "foods": foods,
    }


def _check_database(settings: Settings) -> dict[str, Any]:
    """Report whether a database is configured.

    Connectivity is not yet verified because the persistence layer does not
    exist. This check reports configuration only, and will perform a real
    connection test once repositories are implemented.
    """
    if settings.database_url is None:
        return {"status": ComponentStatus.NOT_CONFIGURED}
    return {"status": ComponentStatus.OK, "detail": "configured, not yet verified"}


def _check_ai_provider(settings: Settings) -> dict[str, Any]:
    """Report whether an AI provider is configured.

    Non-blocking by design: an unavailable provider never makes the service
    unready, because the rest of the product keeps working without it.
    """
    if settings.groq_api_key is None:
        return {"status": ComponentStatus.NOT_CONFIGURED, "model": settings.ai_model}
    return {"status": ComponentStatus.OK, "model": settings.ai_model}


@router.get("/live", summary="Liveness probe")
async def live() -> dict[str, Any]:
    """Report that the process is running.

    Deliberately checks nothing else: a liveness probe that fails on a
    dependency outage would have the platform restart a healthy process.
    """
    return success("Service is live.", {"status": ComponentStatus.OK})


@router.get("/ready", summary="Readiness probe")
async def ready(response: Response, settings: SettingsDep) -> dict[str, Any]:
    """Report whether the service can handle traffic.

    Readiness depends on configuration and the business engines. A missing
    database or AI provider is reported but does not block readiness, so the
    backend still serves what it can.
    """
    engines = _check_engines()
    is_ready = engines["status"] is ComponentStatus.OK

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return success(
        "Service is ready." if is_ready else "Service is not ready.",
        {
            "ready": is_ready,
            "configuration": _check_configuration(settings),
            "engines": engines,
        },
    )


@router.get("/health", summary="Detailed health report")
async def health(response: Response, settings: SettingsDep) -> dict[str, Any]:
    """Report the state of every checked component."""
    engines = _check_engines()
    healthy = engines["status"] is ComponentStatus.OK

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return success(
        "Service is healthy." if healthy else "Service is degraded.",
        {
            "healthy": healthy,
            "application": settings.app_name,
            "components": {
                "configuration": _check_configuration(settings),
                "engines": engines,
                "database": _check_database(settings),
                "ai_provider": _check_ai_provider(settings),
            },
        },
    )
