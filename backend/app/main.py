# file_name: main.py

"""FastAPI application factory.

Wires configuration, logging, middleware, exception handling and routing into a
single application, following ``docs/04_backend/28_BACKEND_ARCHITECTURE.md``.

Startup validates configuration and warms the configuration-driven engines.
``docs/03_business/19_EXERCISE_ENGINE.md`` section 8 and
``docs/03_business/24_FOOD_CATALOG_ENGINE.md`` section 7 both require the
application to refuse to start when configuration is invalid, so the registries
are loaded here rather than lazily on the first request.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.middleware import RequestContextMiddleware
from app.api.v1 import api_router
from app.core.config import Settings, get_settings
from app.core.logging_config import configure_logging
from app.engines.exercise.catalog import load_exercise_registry
from app.engines.nutrition import load_food_registry
from app.engines.nutrition.diet_rules import load_cached_diet_rules
from app.engines.workout import load_workout_templates
from app.infrastructure.database.session import (
    configure_from_settings,
    dispose_database,
    get_session,
    is_configured,
)
from app.infrastructure.auth.google_identity import GoogleOAuthIdentityProvider
from app.infrastructure.seed import seed_if_empty

logger = logging.getLogger(__name__)

API_TITLE = "GymVision AI"
API_DESCRIPTION = (
    "Real-time posture analysis, workout generation and nutrition planning."
)
API_VERSION = "1.0.0"


def _warm_engines() -> None:
    """Load and validate every configuration-driven engine.

    Raises:
        GymVisionError: If any configuration file is missing or invalid.
    """
    exercises = len(load_exercise_registry())
    workouts = len(load_workout_templates())
    foods = len(load_food_registry())
    load_cached_diet_rules()

    logger.info(
        "Configuration loaded: %d exercises, %d workout templates, %d foods.",
        exercises,
        workouts,
        foods,
    )


async def _warm_google_certificates(settings: Settings) -> None:
    """Fetch Google's signing certificates before anyone tries to sign in.

    ``google-auth`` fetches them on every verification, and on a host with a
    slow route to ``www.googleapis.com`` that round trip dominates sign-in.
    Paying it once here, off the event loop, keeps it out of the login request.

    Run as a background task rather than awaited during startup. Awaiting it
    held the server closed for as long as the fetch took — around eighty seconds
    on a host whose route to Google is slow — during which nothing was listening
    and every request failed. A warm cache is an optimisation, never a condition
    for serving.

    A failure is logged rather than fatal: the fetch is retried on first use.
    """
    if settings.google_client_id is None:
        return

    try:
        # The certificate cache is process-wide, so this throwaway provider
        # warms the very cache the per-request providers will read.
        provider = GoogleOAuthIdentityProvider(settings)
        await asyncio.to_thread(provider.warm_certificate_cache)
        logger.info("Google certificates preloaded.")
    except Exception:
        logger.warning(
            "Could not preload Google's certificates; the first sign-in will "
            "fetch them.",
            exc_info=True,
        )


async def _seed_libraries_if_needed() -> None:
    """Seed the exercise and food libraries when the database has none.

    A migrated but unseeded database otherwise looks healthy and then fails
    confusingly the first time a workout is generated. Seeding is idempotent and
    matches on slug, so this is safe to attempt on every start.

    A failure here is logged rather than fatal: the service can still serve
    everything that does not need the libraries, and ``/health`` reports the
    state.
    """
    if not is_configured():
        return

    try:
        async for session in get_session():
            written = await seed_if_empty(session)
            if written:
                logger.info(
                    "Seeded %d exercises and %d foods.",
                    written["exercises"],
                    written["foods"],
                )
            break
    except Exception:
        logger.exception("Could not seed the libraries from configuration.")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Validate configuration on startup and log the application lifecycle."""
    settings = getattr(application.state, "settings", None) or get_settings()

    logger.info("Starting %s in %s.", settings.app_name, settings.environment)
    settings.validate_for_runtime()
    _warm_engines()
    configure_from_settings(settings)
    await _seed_libraries_if_needed()

    # Deliberately not awaited: see `_warm_google_certificates`. The reference is
    # held so the task is not garbage collected mid-flight.
    warm_up = asyncio.create_task(_warm_google_certificates(settings))

    missing = settings.missing_secrets()
    if missing:
        # Never log the values, only which ones are absent.
        logger.warning(
            "Running without credentials: %s. Dependent features are unavailable.",
            ", ".join(sorted(missing)),
        )

    logger.info("Startup complete.")
    yield

    warm_up.cancel()
    await dispose_database()
    logger.info("Shutdown complete.")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    Args:
        settings: Configuration override, used by tests. Defaults to the
            environment-derived settings.

    Returns:
        A configured application ready to serve requests.
    """
    supplied = settings is not None
    settings = settings or get_settings()
    configure_logging(settings)

    application = FastAPI(
        title=API_TITLE,
        description=API_DESCRIPTION,
        version=API_VERSION,
        lifespan=lifespan,
        docs_url=settings.docs_url,
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    register_exception_handlers(application)

    application.include_router(health_router)
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    application.state.settings = settings
    if supplied:
        # Explicit settings must reach the dependencies too, otherwise routes
        # would silently keep reading the process environment.
        application.dependency_overrides[get_settings] = lambda: settings

    return application


app = create_app()
