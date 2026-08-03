# file_name: test_startup.py

"""Startup behaviour of the application lifespan."""

import asyncio
import time

import pytest

from app import main


@pytest.mark.asyncio
async def test_startup_does_not_wait_for_googles_certificates(monkeypatch):
    """Preloading must never hold the server closed.

    Awaiting the certificate fetch during startup kept the port shut for as long
    as it took — around eighty seconds on a host with a slow route to Google —
    and every request in that window failed with a non-JSON proxy error rather
    than anything the API had produced.
    """
    started = asyncio.Event()

    async def slow_warm_up(_settings) -> None:
        started.set()
        await asyncio.sleep(30)

    monkeypatch.setattr(main, "_warm_google_certificates", slow_warm_up)
    monkeypatch.setattr(main, "_seed_libraries_if_needed", _noop)

    application = main.create_app()

    began = time.monotonic()
    async with application.router.lifespan_context(application):
        elapsed = time.monotonic() - began

        # Startup returned without waiting. The task is scheduled at this point
        # but has not been given a slice yet, so yield once to let it begin.
        assert elapsed < 5, f"startup blocked for {elapsed:.1f}s"
        await asyncio.sleep(0)
        assert started.is_set(), "the warm-up was never started"


async def _noop() -> None:
    """Stand in for seeding, which needs a configured database."""
