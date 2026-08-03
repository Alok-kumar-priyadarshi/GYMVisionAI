# file_name: cli.py

"""Operational commands.

    python -m app.cli bootstrap    Create the schema and seed the libraries
    python -m app.cli seed         Seed the libraries only
    python -m app.cli check        Report what is configured

Schema changes go through Alembic. ``bootstrap`` runs ``alembic upgrade head``
rather than creating tables directly, so a development database and a deployed
one are built the same way.
"""

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.engines.exercise.catalog import load_exercise_registry
from app.engines.nutrition import load_food_registry
from app.engines.workout import load_workout_templates
from app.infrastructure.database.session import (
    configure_from_settings,
    dispose_database,
)
from app.infrastructure.seed import seed_all

logger = logging.getLogger("gymvision.cli")

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _require_database() -> None:
    """Stop with a clear message when no database is configured."""
    if get_settings().database_url is None:
        sys.exit(
            "DATABASE_URL is not set.\n"
            "Copy .env.example to .env and set it, for example:\n"
            "  DATABASE_URL=sqlite+aiosqlite:///./gymvision.db"
        )


def migrate() -> None:
    """Apply every pending migration."""
    _require_database()
    logger.info("Applying migrations.")

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
    )
    if result.returncode != 0:
        sys.exit("Migrations failed. See the output above.")


async def _seed() -> dict[str, int]:
    """Write the configured libraries into the database."""
    engine = configure_from_settings()
    if engine is None:
        sys.exit("DATABASE_URL is not set.")

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        written = await seed_all(session)
        await session.commit()

    await dispose_database()
    return written


def seed() -> None:
    """Seed the exercise and food libraries."""
    _require_database()
    written = asyncio.run(_seed())
    print(f"Seeded {written['exercises']} exercises and {written['foods']} foods.")


def bootstrap() -> None:
    """Prepare a database from nothing: migrate, then seed."""
    migrate()
    seed()
    print("\nThe database is ready. Start the API with:")
    print("  python -m uvicorn app.main:app --reload")


def check() -> None:
    """Report what is configured, without revealing any secret."""
    settings = get_settings()
    missing = set(settings.missing_secrets())

    print(f"Environment:  {settings.environment}")
    print(f"Exercises:    {len(load_exercise_registry())}")
    print(f"Workouts:     {len(load_workout_templates())} templates")
    print(f"Foods:        {len(load_food_registry())}")
    print()

    for name, purpose in (
        ("database_url", "persistence, workouts, progress"),
        ("jwt_secret_key", "signing sessions"),
        ("google_client_id", "sign-in"),
        ("google_client_secret", "sign-in"),
        ("groq_api_key", "the AI coach"),
    ):
        mark = "not set" if name in missing else "set"
        print(f"  {name:22} {mark:8} {purpose}")

    if missing:
        print("\nFeatures needing an unset value are unavailable until it is set.")


COMMANDS = {
    "bootstrap": bootstrap,
    "migrate": migrate,
    "seed": seed,
    "check": check,
}


def main() -> None:
    """Run one command."""
    configure_logging(get_settings())

    command = sys.argv[1] if len(sys.argv) > 1 else ""
    handler = COMMANDS.get(command)

    if handler is None:
        sys.exit(f"Usage: python -m app.cli [{' | '.join(COMMANDS)}]")

    handler()


if __name__ == "__main__":
    main()
