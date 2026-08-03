# file_name: test_api_foundation.py

"""Integration tests for the API foundation.

Verifies the response envelope, error handling, request correlation, health
endpoints and versioning against the real application.
"""

import pytest
from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging_config import REQUEST_ID_HEADER
from app.main import create_app
from app.shared.exceptions import (
    ExerciseNotFoundError,
    UnsupportedExerciseError,
    WorkoutGenerationError,
)


def bare_settings(**overrides) -> Settings:
    """Settings with nothing configured.

    Built explicitly rather than from the ambient environment: a developer with
    a populated `.env` would otherwise change what these tests assert, and the
    suite must describe the code, not the machine it runs on.
    """
    defaults = {
        "environment": "development",
        "google_client_id": None,
        "google_client_secret": None,
        "groq_api_key": None,
        "database_url": None,
        "jwt_secret_key": None,
    }
    return Settings(**{**defaults, **overrides})


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(create_app(bare_settings())) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def probe_client() -> TestClient:
    """A client with routes that raise, to exercise the error handlers."""
    application = create_app(bare_settings())
    router = APIRouter()

    @router.get("/domain-error")
    async def domain_error():
        raise ExerciseNotFoundError("Exercise 'bench_press' not found.")

    @router.get("/unsupported")
    async def unsupported():
        raise UnsupportedExerciseError("Exercise 'bench_press' is not supported.")

    @router.get("/server-error")
    async def server_error():
        raise WorkoutGenerationError()

    @router.get("/crash")
    async def crash():
        raise RuntimeError("database password is hunter2")

    @router.get("/teapot")
    async def teapot():
        raise HTTPException(status_code=403)

    @router.get("/validated")
    async def validated(count: int):
        return {"count": count}

    application.include_router(router)
    with TestClient(application, raise_server_exceptions=False) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/live", "/ready", "/health"])
def test_health_endpoints_are_public_and_healthy(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_liveness_reports_the_process_is_running(client):
    assert client.get("/live").json()["data"]["status"] == "ok"


def test_readiness_reports_the_loaded_engines(client):
    engines = client.get("/ready").json()["data"]["engines"]

    assert engines["status"] == "ok"
    assert engines["exercises"] == 29
    assert engines["workout_templates"] == 3
    assert engines["foods"] == 36


def test_health_reports_every_component(client):
    components = client.get("/health").json()["data"]["components"]

    assert set(components) == {"configuration", "engines", "database", "ai_provider"}


def test_health_reports_absent_dependencies_without_failing(client):
    components = client.get("/health").json()["data"]["components"]

    assert components["database"]["status"] == "not_configured"
    assert components["ai_provider"]["status"] == "not_configured"
    assert client.get("/health").json()["data"]["healthy"] is True


def test_health_names_missing_secrets_but_never_their_values(client):
    configuration = client.get("/health").json()["data"]["components"]["configuration"]

    assert "jwt_secret_key" in configuration["missing_secrets"]
    assert "SecretStr" not in response_text(client)


def response_text(client: TestClient) -> str:
    return client.get("/health").text


# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------


def test_success_responses_use_the_contract_envelope(client):
    payload = client.get("/live").json()

    assert set(payload) == {"success", "message", "data"}
    assert payload["message"].endswith(".")


def test_error_responses_use_the_contract_envelope(probe_client):
    payload = probe_client.get("/domain-error").json()

    assert set(payload) == {"success", "error"}
    assert set(payload["error"]) == {"code", "message"}
    assert payload["success"] is False


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_a_domain_error_maps_to_its_documented_code(probe_client):
    response = probe_client.get("/domain-error")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXERCISE-001"


def test_a_client_error_maps_to_its_documented_code(probe_client):
    response = probe_client.get("/unsupported")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EXERCISE-005"


def test_a_server_side_domain_error_is_reported(probe_client):
    response = probe_client.get("/server-error")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "WORKOUT-002"


def test_an_unexpected_error_never_leaks_internals(probe_client):
    response = probe_client.get("/crash")

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "error": {"code": "SYSTEM-001", "message": "Internal server error."},
    }
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text


def test_a_framework_error_maps_to_a_documented_code(probe_client):
    response = probe_client.get("/teapot")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH-005"


def test_an_unknown_route_returns_the_documented_message(client):
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == (
        "The requested resource was not found."
    )


def test_invalid_input_returns_a_validation_error(probe_client):
    response = probe_client.get("/validated", params={"count": "many"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION-003"
    assert "count" in response.json()["error"]["message"]


def test_validation_errors_do_not_echo_submitted_values(probe_client):
    response = probe_client.get("/validated", params={"count": "secret-token"})

    assert "secret-token" not in response.text


# ---------------------------------------------------------------------------
# Request correlation
# ---------------------------------------------------------------------------


def test_every_response_carries_a_request_id(client):
    assert client.get("/live").headers[REQUEST_ID_HEADER]


def test_request_ids_are_unique_per_request(client):
    first = client.get("/live").headers[REQUEST_ID_HEADER]
    second = client.get("/live").headers[REQUEST_ID_HEADER]

    assert first != second


def test_a_supplied_request_id_is_reused(client):
    response = client.get("/live", headers={REQUEST_ID_HEADER: "trace-123"})

    assert response.headers[REQUEST_ID_HEADER] == "trace-123"


def test_an_oversized_request_id_is_truncated(client):
    response = client.get("/live", headers={REQUEST_ID_HEADER: "x" * 500})

    assert len(response.headers[REQUEST_ID_HEADER]) == 128


# ---------------------------------------------------------------------------
# Versioning and documentation
# ---------------------------------------------------------------------------


def test_feature_routes_are_served_under_the_version_prefix():
    # No feature router exists yet, so mount one to prove the prefix is wired.
    application = create_app(bare_settings())
    router = APIRouter()

    @router.get("/ping")
    async def ping():
        return {"ok": True}

    application.include_router(router, prefix=Settings().api_v1_prefix)

    with TestClient(application) as versioned:
        assert versioned.get("/api/v1/ping").status_code == 200
        assert versioned.get("/ping").status_code == 404


@pytest.mark.parametrize("path", ["/live", "/ready", "/health"])
def test_health_routes_are_not_versioned(client, path):
    # Platform probes call these directly, without the product's version prefix.
    assert client.get(path).status_code == 200
    assert client.get(f"/api/v1{path}").status_code == 404


def test_openapi_is_generated_outside_production(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "GymVision AI"


def test_production_hides_the_schema_and_documentation():
    production = Settings(
        environment="production",
        google_client_id="id",
        google_client_secret="secret",
        groq_api_key="key",
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret_key="a-test-signing-key-of-sufficient-length",
    )

    with TestClient(create_app(production)) as production_client:
        assert production_client.get("/openapi.json").status_code == 404
        assert production_client.get("/docs").status_code == 404


def test_cors_headers_are_returned_for_a_trusted_origin(client):
    response = client.get("/live", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_an_untrusted_origin_receives_no_cors_grant(client):
    response = client.get("/live", headers={"Origin": "http://evil.test"})

    assert "access-control-allow-origin" not in response.headers
