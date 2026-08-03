# file_name: test_diet_endpoints.py

"""Diet endpoints, per ``contracts/diet/``.

These run against a real database so the storage path is exercised, not mocked:
the point of the feature is that a plan survives being generated.
"""

import pytest


def generate(client, headers, **body):
    return client.post("/api/v1/diet/generate", headers=headers, json=body or {})


def test_a_plan_is_generated_from_the_profile(client, profiled_headers):
    response = generate(client, profiled_headers)

    assert response.status_code == 201, response.text
    plan = response.json()["data"]

    assert plan["dietPlanId"]
    assert plan["estimatedCalories"] > 0
    assert plan["waterTargetMl"] > 0
    assert plan["meals"], "a plan with no meals is not a recommendation"

    for meal in plan["meals"]:
        assert meal["items"], f"{meal['mealType']} has no food in it"
        for item in meal["items"]:
            assert item["servings"] > 0
            assert item["name"]
            assert item["servingSize"]


def test_the_plan_is_readable_afterwards(client, profiled_headers):
    """The whole point of storing it: a plan is not a one-off answer."""
    created = generate(client, profiled_headers).json()["data"]

    response = client.get("/api/v1/diet/current", headers=profiled_headers)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["dietPlanId"] == created["dietPlanId"]


def test_totals_agree_with_the_items(client, profiled_headers):
    # A totals row that disagrees with the rows above it is worse than none.
    plan = generate(client, profiled_headers).json()["data"]

    expected = sum(
        item["calories"] for meal in plan["meals"] for item in meal["items"]
    )

    assert plan["totals"]["calories"] == pytest.approx(expected, abs=0.5)


def test_a_user_with_no_plan_is_told_so(client, profiled_headers):
    response = client.get("/api/v1/diet/current", headers=profiled_headers)

    # Not a failure: the client offers to generate one.
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DIET-001"


def test_a_profile_is_required(client, auth_headers):
    response = generate(client, auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER-002"


def test_regenerating_archives_the_previous_plan(client, profiled_headers):
    first = generate(client, profiled_headers).json()["data"]["dietPlanId"]
    second = generate(client, profiled_headers).json()["data"]["dietPlanId"]

    assert first != second

    current = client.get("/api/v1/diet/current", headers=profiled_headers)
    assert current.json()["data"]["dietPlanId"] == second

    # The old plan is archived, not deleted, so it stays readable.
    archived = client.get(f"/api/v1/diet/{first}", headers=profiled_headers)
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "Archived"


def test_history_lists_every_plan(client, profiled_headers):
    generate(client, profiled_headers)
    generate(client, profiled_headers)

    response = client.get("/api/v1/diet/history", headers=profiled_headers)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]) == 2
    assert payload["pagination"]["total"] == 2
    assert all(entry["mealCount"] > 0 for entry in payload["data"])


def test_history_is_empty_rather_than_missing(client, profiled_headers):
    response = client.get("/api/v1/diet/history", headers=profiled_headers)

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_the_dietary_preference_is_respected(client, profiled_headers):
    response = generate(client, profiled_headers, dietPreference="Vegan")

    assert response.status_code == 201
    assert response.json()["data"]["dietPreference"] == "Vegan"


def test_the_preference_carries_into_the_next_plan(client, profiled_headers):
    """Regenerating must not silently revert a choice the user made."""
    generate(client, profiled_headers, dietPreference="Vegan")

    again = generate(client, profiled_headers)

    assert again.json()["data"]["dietPreference"] == "Vegan"


def test_generation_is_deterministic(client, profiled_headers):
    # Required by `23_DIET_PLANNING_ENGINE.md` section 19.
    first = generate(client, profiled_headers).json()["data"]
    second = generate(client, profiled_headers).json()["data"]

    assert first["estimatedCalories"] == second["estimatedCalories"]
    assert [meal["mealType"] for meal in first["meals"]] == [
        meal["mealType"] for meal in second["meals"]
    ]


def test_another_users_plan_is_reported_as_absent(client, profiled_headers):
    mine = generate(client, profiled_headers).json()["data"]["dietPlanId"]

    other = client.post("/api/v1/auth/google", json={"idToken": "token-bob"})
    headers = {"Authorization": f"Bearer {other.json()['data']['accessToken']}"}

    response = client.get(f"/api/v1/diet/{mine}", headers=headers)

    # Absent, not forbidden: the response must not confirm it exists.
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DIET-001"


def test_authentication_is_required(client):
    assert client.get("/api/v1/diet/current").status_code == 401
    assert client.post("/api/v1/diet/generate", json={}).status_code == 401
