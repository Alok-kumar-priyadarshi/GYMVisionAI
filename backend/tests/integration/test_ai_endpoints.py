# file_name: test_ai_endpoints.py

"""End-to-end tests for the AI endpoints.

The whole pipeline runs for real — intent, context building, prompt assembly,
response validation and the guardrails. Only the network call to Groq is
substituted, because reaching a live model would make these tests
non-deterministic and would need a paid key.

The fake provider records the prompt it received, so these tests also assert
what the pipeline actually sends.
"""

import json

import pytest

from app.core.dependencies import get_ai_provider
from app.engines.ai.provider import AIProvider, ModelInfo, ProviderRequest, ProviderResponse
from app.main import create_app
from tests.integration.conftest import test_settings


class RecordingProvider(AIProvider):
    """Returns a scripted reply and remembers what it was asked."""

    def __init__(self, reply: str = "Keep your core braced and lower under control."):
        self.reply = reply
        self.requests: list[ProviderRequest] = []
        self.error: Exception | None = None

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return ProviderResponse(
            content=self.reply,
            model="fake-model",
            provider="fake",
            finish_reason="stop",
            prompt_tokens=100,
            completion_tokens=50,
        )

    async def health_check(self) -> bool:
        return True

    def model_info(self) -> ModelInfo:
        return ModelInfo(provider="fake", model="fake-model", configured=True)


@pytest.fixture
def provider() -> RecordingProvider:
    return RecordingProvider()


@pytest.fixture
def ai_client(session_factory, provider):
    """An API client whose only fake is the language model itself."""
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.api.routers import exercises as exercises_router
    from app.core.dependencies import get_conversation_memory, get_identity_provider
    from app.engines.ai.conversation_memory import InMemoryConversationMemory
    from app.infrastructure.database.session import get_session
    from tests.integration.conftest import FakeGoogleIdentityProvider

    application = create_app(test_settings())

    async def override_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    memory = InMemoryConversationMemory()
    application.dependency_overrides[get_session] = override_session
    application.dependency_overrides[get_identity_provider] = (
        lambda: FakeGoogleIdentityProvider()
    )
    application.dependency_overrides[get_ai_provider] = lambda: provider
    application.dependency_overrides[get_conversation_memory] = lambda: memory

    exercises_router._LIVE_SESSIONS.clear()

    with TestClient(application) as client:
        yield client

    application.dependency_overrides.clear()


@pytest.fixture
def headers(ai_client) -> dict[str, str]:
    response = ai_client.post("/api/v1/auth/google", json={"idToken": "token-alice"})
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/v1/ai/chat", "/api/v1/ai/explain", "/api/v1/ai/review"])
def test_ai_endpoints_require_authentication(ai_client, path):
    response = ai_client.post(path, json={})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH-001"


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


def test_chat_returns_a_reply(ai_client, headers, provider):
    response = ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": "How do I improve my push-ups?"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["conversationId"] == "conv-1"
    assert data["response"] == provider.reply
    assert data["createdAt"]


def test_the_prompt_carries_the_user_and_the_question(ai_client, headers, provider):
    ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": "Is my plan right for me?"},
    )

    sent = provider.requests[0]
    assert "Alice Tester" in sent.user_prompt
    assert "Is my plan right for me?" in sent.user_prompt
    assert "GymVision AI" in sent.system_prompt


def test_the_prompt_grounds_the_assistant_in_real_capabilities(
    ai_client, headers, provider
):
    ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": "What can you do?"},
    )

    assert "Supported exercises: 29" in provider.requests[0].user_prompt


def test_conversation_history_reaches_the_next_prompt(ai_client, headers, provider):
    ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": "First question"},
    )
    ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": "Second question"},
    )

    second_prompt = provider.requests[1].user_prompt
    assert "Recent Conversation" in second_prompt
    assert "First question" in second_prompt


def test_conversations_do_not_leak_into_each_other(ai_client, headers, provider):
    ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": "About squats"},
    )
    ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-2", "message": "About diet"},
    )

    assert "About squats" not in provider.requests[1].user_prompt


def test_a_users_conversation_is_not_visible_to_another(ai_client, provider):
    alice = ai_client.post("/api/v1/auth/google", json={"idToken": "token-alice"})
    alice_headers = {
        "Authorization": f"Bearer {alice.json()['data']['accessToken']}"
    }
    bob = ai_client.post("/api/v1/auth/google", json={"idToken": "token-bob"})
    bob_headers = {"Authorization": f"Bearer {bob.json()['data']['accessToken']}"}

    ai_client.post(
        "/api/v1/ai/chat",
        headers=alice_headers,
        json={"conversationId": "shared", "message": "Alice's private question"},
    )
    ai_client.post(
        "/api/v1/ai/chat",
        headers=bob_headers,
        json={"conversationId": "shared", "message": "Bob's question"},
    )

    assert "Alice's private question" not in provider.requests[1].user_prompt


def test_an_empty_message_is_rejected(ai_client, headers):
    response = ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": ""},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------


def test_an_exercise_is_explained(ai_client, headers, provider):
    response = ai_client.post(
        "/api/v1/ai/explain", headers=headers, json={"exerciseId": "push_ups"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["exerciseId"] == "push_ups"
    assert data["title"] == "Push-ups"
    assert data["explanation"] == provider.reply


def test_the_explanation_prompt_carries_the_documented_steps(
    ai_client, headers, provider
):
    ai_client.post(
        "/api/v1/ai/explain", headers=headers, json={"exerciseId": "push_ups"}
    )

    prompt = provider.requests[0].user_prompt
    assert "Documented steps" in prompt
    assert "high plank" in prompt
    assert "Chest" in prompt


def test_an_unknown_exercise_cannot_be_explained(ai_client, headers):
    response = ai_client.post(
        "/api/v1/ai/explain", headers=headers, json={"exerciseId": "bench_press"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXERCISE-001"


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


REVIEW_JSON = json.dumps(
    {
        "summary": "You completed every exercise with steady pacing.",
        "strengths": ["Consistent repetition quality", "Good session length"],
        "improvements": ["Hold the plank longer"],
        "motivation": "Strong work. Keep the streak going.",
    }
)


def workout_for(client, headers) -> str:
    client.put(
        "/api/v1/users/profile",
        headers=headers,
        json={
            "age": 30,
            "gender": "Male",
            "heightCm": 178,
            "weightKg": 78,
            "fitnessGoal": "General Fitness",
            "fitnessLevel": "Intermediate",
            "workoutDurationMinutes": 45,
        },
    )
    generated = client.post("/api/v1/workouts/generate", headers=headers)
    return generated.json()["data"]["workoutId"]


def test_a_completed_workout_is_reviewed(ai_client, headers, provider):
    provider.reply = REVIEW_JSON
    workout_id = workout_for(ai_client, headers)

    response = ai_client.post(
        "/api/v1/ai/review", headers=headers, json={"workoutId": workout_id}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["workoutId"] == workout_id
    assert data["summary"].startswith("You completed")
    assert len(data["strengths"]) == 2
    assert data["improvements"] == ["Hold the plank longer"]
    assert data["motivation"]


def test_the_review_prompt_carries_the_workout(ai_client, headers, provider):
    provider.reply = REVIEW_JSON
    workout_for(ai_client, headers)

    ai_client.post(
        "/api/v1/ai/review",
        headers=headers,
        json={"workoutId": workout_for(ai_client, headers)},
    )

    assert "# Current Workout" in provider.requests[-1].user_prompt


def test_another_users_workout_cannot_be_reviewed(ai_client, headers, provider):
    provider.reply = REVIEW_JSON
    workout_id = workout_for(ai_client, headers)

    bob = ai_client.post("/api/v1/auth/google", json={"idToken": "token-bob"})
    bob_headers = {"Authorization": f"Bearer {bob.json()['data']['accessToken']}"}

    response = ai_client.post(
        "/api/v1/ai/review", headers=bob_headers, json={"workoutId": workout_id}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORKOUT-001"


def test_a_malformed_workout_identifier_is_rejected(ai_client, headers):
    response = ai_client.post(
        "/api/v1/ai/review", headers=headers, json={"workoutId": "not-a-uuid"}
    )

    assert response.status_code == 404


def test_a_review_that_is_not_json_is_rejected(ai_client, headers, provider):
    provider.reply = "Great job today, you did really well overall."
    workout_id = workout_for(ai_client, headers)

    response = ai_client.post(
        "/api/v1/ai/review", headers=headers, json={"workoutId": workout_id}
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "AI-003"


# ---------------------------------------------------------------------------
# Guardrails and failures
# ---------------------------------------------------------------------------


def test_an_unsafe_reply_never_reaches_the_user(ai_client, headers, provider):
    provider.reply = "I watched your form and you clearly have a rotator cuff tear."

    response = ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": "My shoulder hurts"},
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "AI-003"
    assert "rotator cuff" not in response.text


def test_a_rejected_reply_is_not_remembered(ai_client, headers, provider):
    provider.reply = "I analysed your squat and it was perfect."
    ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": "How was my squat?"},
    )

    provider.reply = "Focus on keeping your chest tall through the movement."
    ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": "Any tips?"},
    )

    assert "I analysed your squat" not in provider.requests[-1].user_prompt


def test_provider_unavailability_is_reported_cleanly(ai_client, headers, provider):
    from app.shared.exceptions import AIProviderError

    provider.error = AIProviderError()

    response = ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": "Hello"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI-001"


def test_a_provider_timeout_is_reported_cleanly(ai_client, headers, provider):
    from app.shared.exceptions import AITimeoutError

    provider.error = AITimeoutError()

    response = ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": "Hello"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI-002"


def test_the_prompt_never_reaches_the_client_on_failure(ai_client, headers, provider):
    from app.shared.exceptions import AIProviderError

    provider.error = AIProviderError()

    response = ai_client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"conversationId": "conv-1", "message": "Hello"},
    )

    assert "GymVision AI, the fitness assistant" not in response.text
    assert "# User" not in response.text
