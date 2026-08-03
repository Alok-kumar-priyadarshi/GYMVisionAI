# file_name: test_api_endpoints.py

"""End-to-end tests for every implemented API endpoint.

These drive the real application: real routers, real services, real repositories
and a real database schema, with only Google's token verification faked.
"""

import time

import pytest

from app.engines.session.rep_validation import DEFAULT_MINIMUM_SECONDS
from tests.fixtures.landmarks import push_up_pose

MINIMUM_REP_GAP_SECONDS = DEFAULT_MINIMUM_SECONDS + 0.05
"""Just over the validator's floor, so a paced repetition is credited."""

PROTECTED_ENDPOINTS = [
    ("get", "/api/v1/auth/me"),
    ("post", "/api/v1/auth/logout"),
    ("get", "/api/v1/users/profile"),
    ("get", "/api/v1/exercises"),
    ("get", "/api/v1/exercises/history"),
    ("post", "/api/v1/exercises/start"),
    ("post", "/api/v1/workouts/generate"),
    ("get", "/api/v1/workouts/current"),
    ("get", "/api/v1/workouts/history"),
    ("get", "/api/v1/progress"),
    ("get", "/api/v1/progress/dashboard"),
    ("get", "/api/v1/progress/statistics"),
]


def landmark_payload(pose) -> list[dict]:
    """Shape a fixture pose as the frame endpoint expects."""
    return [
        {"x": mark.x, "y": mark.y, "z": mark.z, "visibility": mark.visibility}
        for mark in pose
    ]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), PROTECTED_ENDPOINTS)
def test_every_protected_endpoint_requires_authentication(client, method, path):
    response = (
        client.post(path, json={}) if method == "post" else client.get(path)
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH-001"


def test_google_login_issues_tokens_and_creates_a_user(client):
    response = client.post("/api/v1/auth/google", json={"idToken": "token-alice"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["accessToken"]
    assert data["refreshToken"]
    assert data["expiresIn"] > 0
    assert data["user"]["email"] == "alice@test.com"


def test_google_login_is_idempotent_for_a_returning_user(client):
    first = client.post("/api/v1/auth/google", json={"idToken": "token-alice"})
    second = client.post("/api/v1/auth/google", json={"idToken": "token-alice"})

    assert first.json()["data"]["user"]["id"] == second.json()["data"]["user"]["id"]


def test_an_invalid_google_token_is_rejected(client):
    response = client.post("/api/v1/auth/google", json={"idToken": "forged"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH-004"


def test_login_requires_a_token(client):
    assert client.post("/api/v1/auth/google", json={}).status_code == 422


def test_the_current_user_is_returned(client, auth_headers):
    response = client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"]["email"] == "alice@test.com"


def test_a_refresh_token_yields_a_new_access_token(client):
    login = client.post("/api/v1/auth/google", json={"idToken": "token-alice"})
    refresh = login.json()["data"]["refreshToken"]

    response = client.post("/api/v1/auth/refresh", json={"refreshToken": refresh})

    assert response.status_code == 200
    assert response.json()["data"]["accessToken"]


def test_an_access_token_cannot_be_used_to_refresh(client, auth_headers):
    access = auth_headers["Authorization"].split()[1]

    response = client.post("/api/v1/auth/refresh", json={"refreshToken": access})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH-002"


def test_a_forged_token_is_rejected(client):
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.token"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH-002"


def test_logout_succeeds(client, auth_headers):
    response = client.post("/api/v1/auth/logout", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"] is None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def test_a_profile_is_created_then_returned(client, auth_headers):
    created = client.put(
        "/api/v1/users/profile",
        headers=auth_headers,
        json={
            "age": 28,
            "gender": "Female",
            "heightCm": 165,
            "weightKg": 62,
            "fitnessGoal": "Weight Loss",
            "fitnessLevel": "Beginner",
        },
    )
    assert created.status_code == 200

    fetched = client.get("/api/v1/users/profile", headers=auth_headers)
    assert fetched.status_code == 200
    data = fetched.json()["data"]
    assert data["fitnessGoal"] == "Weight Loss"
    assert data["bmi"] == pytest.approx(22.8, abs=0.1)


def test_a_missing_profile_is_reported(client, auth_headers):
    response = client.get("/api/v1/users/profile", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER-002"


def test_a_profile_can_be_replaced(client, profiled_headers):
    client.put(
        "/api/v1/users/profile",
        headers=profiled_headers,
        json={
            "age": 31,
            "gender": "Male",
            "heightCm": 178,
            "weightKg": 74,
            "fitnessGoal": "Muscle Gain",
            "fitnessLevel": "Advanced",
        },
    )

    data = client.get("/api/v1/users/profile", headers=profiled_headers).json()["data"]
    assert data["fitnessGoal"] == "Muscle Gain"
    assert data["weightKg"] == 74


def test_an_implausible_profile_is_rejected(client, auth_headers):
    response = client.put(
        "/api/v1/users/profile",
        headers=auth_headers,
        json={
            "age": 5,
            "gender": "Male",
            "heightCm": 178,
            "weightKg": 74,
            "fitnessGoal": "Muscle Gain",
            "fitnessLevel": "Advanced",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION-003"


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------


def test_the_exercise_library_is_returned(client, auth_headers):
    response = client.get("/api/v1/exercises", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 29
    assert all(item["detectorAvailable"] for item in data)
    assert {"exerciseId", "name", "category", "difficulty", "exerciseType"} <= set(
        data[0]
    )


def test_one_exercise_is_returned_with_full_metadata(client, auth_headers):
    response = client.get("/api/v1/exercises/push_ups", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Push-ups"
    assert data["primaryMuscles"]
    assert len(data["instructions"]) >= 3


def test_an_unknown_exercise_is_reported(client, auth_headers):
    response = client.get("/api/v1/exercises/bench_press", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXERCISE-001"


def test_a_session_runs_from_start_to_finish(client, auth_headers):
    started = client.post(
        "/api/v1/exercises/start",
        headers=auth_headers,
        json={"exerciseId": "push_ups"},
    )
    assert started.status_code == 201
    session_id = started.json()["data"]["sessionId"]

    for index, angle in enumerate((180, 60, 180, 60)):
        # Repetitions are validated against a minimum duration, so frames sent
        # back to back would be rejected as detector noise -- correctly, since
        # nobody performs two push-ups in a hundredth of a second. The pause
        # makes the pace a human one.
        if index:
            time.sleep(MINIMUM_REP_GAP_SECONDS)

        frame = client.post(
            "/api/v1/exercises/frame",
            headers=auth_headers,
            json={
                "sessionId": session_id,
                "landmarks": landmark_payload(push_up_pose(angle)),
            },
        )
        assert frame.status_code == 200

    assert frame.json()["data"]["reps"] == 2

    ended = client.post(
        "/api/v1/exercises/end",
        headers=auth_headers,
        json={"sessionId": session_id},
    )
    assert ended.status_code == 200
    assert ended.json()["data"]["totalReps"] == 2
    assert ended.json()["data"]["status"] == "Completed"


def test_a_session_with_no_repetitions_is_not_completed(client, auth_headers):
    """Opening the camera and closing it again is not doing the exercise.

    Recording it as completed would tick the exercise off the workout and count
    towards the user's totals on the strength of no work at all.
    """
    started = client.post(
        "/api/v1/exercises/start",
        headers=auth_headers,
        json={"exerciseId": "push_ups"},
    )
    session_id = started.json()["data"]["sessionId"]

    ended = client.post(
        "/api/v1/exercises/end",
        headers=auth_headers,
        json={"sessionId": session_id},
    )

    assert ended.status_code == 200
    assert ended.json()["data"]["totalReps"] == 0
    assert ended.json()["data"]["status"] == "Stopped"


def test_only_one_session_may_be_active(client, auth_headers):
    client.post(
        "/api/v1/exercises/start",
        headers=auth_headers,
        json={"exerciseId": "push_ups"},
    )
    second = client.post(
        "/api/v1/exercises/start",
        headers=auth_headers,
        json={"exerciseId": "plank"},
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "EXERCISE-003"


def test_an_unsupported_exercise_cannot_start_a_session(client, auth_headers):
    response = client.post(
        "/api/v1/exercises/start",
        headers=auth_headers,
        json={"exerciseId": "arm_circles"},
    )

    assert response.status_code == 404


def test_a_frame_for_an_unknown_session_is_rejected(client, auth_headers):
    response = client.post(
        "/api/v1/exercises/frame",
        headers=auth_headers,
        json={
            "sessionId": "018f95f5-67d4-7d7c-b8c0-5d6d2b62b4e7",
            "landmarks": landmark_payload(push_up_pose(180)),
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXERCISE-002"


def test_a_frame_without_landmarks_is_rejected(client, auth_headers):
    started = client.post(
        "/api/v1/exercises/start",
        headers=auth_headers,
        json={"exerciseId": "push_ups"},
    )
    session_id = started.json()["data"]["sessionId"]

    response = client.post(
        "/api/v1/exercises/frame",
        headers=auth_headers,
        json={"sessionId": session_id, "landmarks": []},
    )

    assert response.status_code == 422


def test_another_users_session_is_not_reachable(client, auth_headers):
    started = client.post(
        "/api/v1/exercises/start",
        headers=auth_headers,
        json={"exerciseId": "push_ups"},
    )
    session_id = started.json()["data"]["sessionId"]

    bob = client.post("/api/v1/auth/google", json={"idToken": "token-bob"})
    bob_headers = {"Authorization": f"Bearer {bob.json()['data']['accessToken']}"}

    response = client.get(
        f"/api/v1/exercises/sessions/{session_id}", headers=bob_headers
    )

    assert response.status_code == 404


def test_session_history_is_returned(client, auth_headers):
    started = client.post(
        "/api/v1/exercises/start",
        headers=auth_headers,
        json={"exerciseId": "push_ups"},
    )
    client.post(
        "/api/v1/exercises/end",
        headers=auth_headers,
        json={"sessionId": started.json()["data"]["sessionId"]},
    )

    response = client.get("/api/v1/exercises/history", headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------


def test_a_workout_is_generated_and_persisted(client, profiled_headers):
    generated = client.post("/api/v1/workouts/generate", headers=profiled_headers)

    assert generated.status_code == 201
    data = generated.json()["data"]
    assert data["exerciseCount"] > 0
    assert data["estimatedDurationMinutes"] <= 45

    current = client.get("/api/v1/workouts/current", headers=profiled_headers)
    assert current.status_code == 200
    assert current.json()["data"]["workoutId"] == data["workoutId"]
    assert len(current.json()["data"]["exercises"]) == data["exerciseCount"]


def test_generation_requires_a_profile(client, auth_headers):
    response = client.post("/api/v1/workouts/generate", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER-002"


def test_a_generated_workout_names_real_exercises(client, profiled_headers):
    client.post("/api/v1/workouts/generate", headers=profiled_headers)
    current = client.get("/api/v1/workouts/current", headers=profiled_headers)

    for item in current.json()["data"]["exercises"]:
        assert item["slug"]
        assert item["name"]
        assert item["sets"] >= 1


def test_no_current_workout_is_reported(client, auth_headers):
    response = client.get("/api/v1/workouts/current", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORKOUT-001"


PROFILE = {
    "age": 30,
    "gender": "Male",
    "heightCm": 178,
    "weightKg": 78,
    "fitnessGoal": "General Fitness",
    "fitnessLevel": "Intermediate",
    "problemAreas": ["belly"],
    "workoutDurationMinutes": 45,
}


def test_regenerating_an_unchanged_profile_does_not_duplicate(
    client, profiled_headers
):
    """Generation is deterministic, so the same profile yields the same plan.

    Storing it again filled the user's history with identical plans while the
    screen appeared not to react at all, which read as a broken button.
    """
    first = client.post("/api/v1/workouts/generate", headers=profiled_headers)
    assert first.status_code == 201
    assert first.json()["data"]["unchanged"] is False

    again = client.post("/api/v1/workouts/generate", headers=profiled_headers)

    assert again.status_code == 200
    assert again.json()["data"]["unchanged"] is True
    assert again.json()["data"]["workoutId"] == first.json()["data"]["workoutId"]
    assert "unchanged" in again.json()["message"]

    history = client.get("/api/v1/workouts/history", headers=profiled_headers)
    assert history.json()["pagination"]["total"] == 1


def test_changing_the_profile_produces_a_new_plan(client, profiled_headers):
    # The documented way to get a different workout: change what it is built
    # from.
    client.post("/api/v1/workouts/generate", headers=profiled_headers)

    client.put(
        "/api/v1/users/profile",
        headers=profiled_headers,
        json={**PROFILE, "fitnessGoal": "Weight Loss"},
    )
    changed = client.post("/api/v1/workouts/generate", headers=profiled_headers)

    assert changed.status_code == 201
    assert changed.json()["data"]["unchanged"] is False


def test_workout_history_is_paginated(client, profiled_headers):
    for goal in ("General Fitness", "Weight Loss", "Muscle Gain"):
        client.put(
            "/api/v1/users/profile",
            headers=profiled_headers,
            json={**PROFILE, "fitnessGoal": goal},
        )
        client.post("/api/v1/workouts/generate", headers=profiled_headers)

    response = client.get(
        "/api/v1/workouts/history", headers=profiled_headers, params={"limit": 2}
    )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 2
    assert response.json()["pagination"]["total"] == 3
    assert response.json()["pagination"]["pages"] == 2


def test_a_workout_can_be_fetched_and_deleted(client, profiled_headers):
    generated = client.post("/api/v1/workouts/generate", headers=profiled_headers)
    workout_id = generated.json()["data"]["workoutId"]

    fetched = client.get(f"/api/v1/workouts/{workout_id}", headers=profiled_headers)
    assert fetched.status_code == 200

    deleted = client.delete(f"/api/v1/workouts/{workout_id}", headers=profiled_headers)
    assert deleted.status_code == 200

    assert (
        client.get(
            f"/api/v1/workouts/{workout_id}", headers=profiled_headers
        ).status_code
        == 404
    )


def test_another_users_workout_is_not_reachable(client, profiled_headers):
    generated = client.post("/api/v1/workouts/generate", headers=profiled_headers)
    workout_id = generated.json()["data"]["workoutId"]

    bob = client.post("/api/v1/auth/google", json={"idToken": "token-bob"})
    bob_headers = {"Authorization": f"Bearer {bob.json()['data']['accessToken']}"}

    assert (
        client.get(f"/api/v1/workouts/{workout_id}", headers=bob_headers).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/workouts/{workout_id}", headers=bob_headers).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


def test_a_new_user_starts_with_empty_progress(client, auth_headers):
    response = client.get("/api/v1/progress", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["currentStreak"] == 0
    assert data["totalWorkouts"] == 0
    assert data["lastWorkoutDate"] is None


def test_the_dashboard_summarises_the_account(client, profiled_headers):
    client.post("/api/v1/workouts/generate", headers=profiled_headers)

    response = client.get("/api/v1/progress/dashboard", headers=profiled_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user"]["email"] == "alice@test.com"
    assert data["hasProfile"] is True
    assert data["currentWorkout"] is not None


def test_the_dashboard_works_without_a_profile(client, auth_headers):
    response = client.get("/api/v1/progress/dashboard", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"]["hasProfile"] is False
    assert response.json()["data"]["currentWorkout"] is None


def test_statistics_aggregate_completed_sessions(client, auth_headers):
    started = client.post(
        "/api/v1/exercises/start",
        headers=auth_headers,
        json={"exerciseId": "push_ups"},
    )
    session_id = started.json()["data"]["sessionId"]
    for angle in (180, 60):
        client.post(
            "/api/v1/exercises/frame",
            headers=auth_headers,
            json={
                "sessionId": session_id,
                "landmarks": landmark_payload(push_up_pose(angle)),
            },
        )
    client.post(
        "/api/v1/exercises/end", headers=auth_headers, json={"sessionId": session_id}
    )

    response = client.get("/api/v1/progress/statistics", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"]["completedSessions"] == 1
    assert response.json()["data"]["totalReps"] == 1


# ---------------------------------------------------------------------------
# Contract compliance
# ---------------------------------------------------------------------------


def test_every_success_response_uses_the_contract_envelope(client, auth_headers):
    for path in ("/api/v1/auth/me", "/api/v1/exercises", "/api/v1/progress"):
        payload = client.get(path, headers=auth_headers).json()
        assert set(payload) == {"success", "message", "data"}
        assert payload["success"] is True


def test_responses_use_camel_case_fields(client, auth_headers):
    data = client.get("/api/v1/auth/me", headers=auth_headers).json()["data"]

    assert "createdAt" in data
    assert "created_at" not in data


def test_openapi_documents_every_endpoint(client):
    spec = client.get("/openapi.json").json()

    documented = set(spec["paths"])
    assert "/api/v1/auth/google" in documented
    assert "/api/v1/exercises" in documented
    assert "/api/v1/workouts/generate" in documented
    assert len(documented) >= 18
