# file_name: test_ai_engine.py

"""Unit tests for the AI engine components."""

import json
from uuid import uuid4

import pytest

from app.engines.ai.context_package import (
    ApplicationContext,
    ContextPackage,
    ConversationContext,
    ExerciseContext,
    Intent,
    Message,
    ProgressContext,
    SessionSummaryContext,
    UserContext,
    WorkoutContext,
)
from app.engines.ai.conversation_memory import (
    ASSISTANT_ROLE,
    USER_ROLE,
    InMemoryConversationMemory,
)
from app.engines.ai.prompt_builder import (
    MAX_PROMPT_CHARACTERS,
    PromptBuilder,
    load_prompt_templates,
)
from app.engines.ai.provider import GroqProvider, ProviderRequest, ProviderResponse
from app.engines.ai.response_validator import ResponseValidator
from app.shared.exceptions import (
    AIProviderError,
    AIResponseError,
    PromptConstructionError,
)


@pytest.fixture(scope="module")
def templates() -> dict:
    return load_prompt_templates()


@pytest.fixture
def builder(templates) -> PromptBuilder:
    return PromptBuilder(templates)


def full_package(intent: Intent = Intent.CHAT) -> ContextPackage:
    return ContextPackage(
        intent=intent,
        user=UserContext(
            name="Alice",
            goal="Weight Loss",
            fitness_level="Beginner",
            workout_duration_minutes=30,
            problem_areas=("belly",),
        ),
        exercise=ExerciseContext(
            slug="push_ups",
            name="Push-ups",
            category="Upper Body",
            difficulty="Intermediate",
            exercise_type="Repetition",
            equipment=("none",),
            primary_muscles=("Chest", "Triceps"),
            instructions=("Start in a high plank.", "Lower your chest."),
        ),
        workout=WorkoutContext(
            title="Fat Burn Circuit",
            goal="Weight Loss",
            difficulty="Beginner",
            estimated_duration_minutes=25,
            exercise_names=("Push-ups", "Plank"),
        ),
        sessions=(
            SessionSummaryContext(
                exercise_name="Push-ups",
                repetitions=12,
                duration_seconds=95,
                average_accuracy=91,
                common_feedback=("Good form",),
            ),
        ),
        progress=ProgressContext(
            current_streak=3, longest_streak=7, total_workouts=12, total_minutes=340
        ),
        conversation=ConversationContext(
            conversation_id="conv-1",
            messages=(Message(role="user", content="Hello"),),
        ),
        application=ApplicationContext(
            supported_exercise_count=29,
            supported_goals=("Weight Loss",),
            capabilities=("Posture analysis",),
        ),
    )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------


def test_templates_cover_every_intent(templates):
    for intent in Intent:
        assert str(intent) in templates["task_prompts"]


def test_the_system_prompt_carries_no_user_context(templates):
    # 02_SYSTEM_PROMPT.md section 2 forbids user data in the system prompt.
    system = templates["system_prompt"].lower()

    for token in ("{", "}", "alice", "conversation history:"):
        assert token not in system


def test_the_system_prompt_states_the_documented_boundaries(templates):
    # Whitespace is collapsed so a line wrap cannot break the assertion.
    system = " ".join(templates["system_prompt"].lower().split())

    assert "you are not a personal trainer, a doctor" in system
    assert "do not generate workout plans or diet plans" in system
    assert "do not diagnose" in system
    assert "never claim to have watched, analysed or measured" in system


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def test_a_prompt_is_assembled_from_the_package(builder):
    prompt = builder.build(full_package(), request="How do I improve?")

    assert prompt.system
    assert "Push-ups" in prompt.user
    assert "How do I improve?" in prompt.user
    assert prompt.intent is Intent.CHAT


def test_prompt_assembly_is_deterministic(builder):
    package = full_package()

    assert builder.build(package, "x").user == builder.build(package, "x").user


def test_only_populated_sections_appear(builder):
    minimal = ContextPackage(intent=Intent.CHAT, user=UserContext(name="Alice"))

    prompt = builder.build(minimal, request="Hi")

    assert "# User" in prompt.user
    assert "# Current Workout" not in prompt.user
    assert "# Progress" not in prompt.user


def test_documented_exercise_steps_reach_the_prompt(builder):
    prompt = builder.build(full_package(Intent.EXPLAIN_EXERCISE))

    assert "Start in a high plank." in prompt.user
    assert "Documented steps" in prompt.user


def test_the_review_prompt_requests_json(builder):
    prompt = builder.build(full_package(Intent.REVIEW_WORKOUT))

    assert "JSON" in prompt.user
    assert "strengths" in prompt.user


def test_an_oversized_prompt_is_rejected(builder):
    huge = ContextPackage(
        intent=Intent.CHAT, user=UserContext(name="A" * MAX_PROMPT_CHARACTERS)
    )

    with pytest.raises(PromptConstructionError):
        builder.build(huge, request="Hi")


def test_a_missing_template_is_rejected():
    partial = PromptBuilder(
        {
            "version": "1.0.0",
            "system_prompt": "system",
            "task_prompts": {"chat": "task"},
        }
    )

    with pytest.raises(PromptConstructionError):
        partial.build(ContextPackage(intent=Intent.REVIEW_WORKOUT))


def test_templates_missing_an_intent_fail_to_load(tmp_path):
    path = tmp_path / "templates.yaml"
    path.write_text(
        "system_prompt: hello\ntask_prompts:\n  chat: task\n", encoding="utf-8"
    )

    with pytest.raises(PromptConstructionError) as error:
        load_prompt_templates(path)

    assert "explain_exercise" in str(error.value)


def test_a_missing_template_file_is_rejected(tmp_path):
    with pytest.raises(PromptConstructionError):
        load_prompt_templates(tmp_path / "absent.yaml")


# ---------------------------------------------------------------------------
# Response validation and safety
# ---------------------------------------------------------------------------


@pytest.fixture
def validator() -> ResponseValidator:
    return ResponseValidator()


def test_a_normal_response_passes(validator):
    text = "Keep your core braced and lower under control."

    assert validator.validate_text(text) == text


@pytest.mark.parametrize("content", ["", "   ", "ok"])
def test_an_empty_or_tiny_response_is_rejected(validator, content):
    with pytest.raises(AIResponseError):
        validator.validate_text(content)


def test_an_oversized_response_is_rejected(validator):
    with pytest.raises(AIResponseError):
        validator.validate_text("word " * 4000)


@pytest.mark.parametrize(
    "content",
    [
        "You have tendinitis in your shoulder.",
        "I diagnose a rotator cuff tear.",
        "Take 400 mg ibuprofen before training.",
    ],
)
def test_medical_claims_are_blocked(validator, content):
    with pytest.raises(AIResponseError):
        validator.validate_text(content)


@pytest.mark.parametrize(
    "content",
    [
        "I watched your form and it looked strong throughout the set.",
        "I analysed your push-ups and your depth was inconsistent.",
        "I measured your elbow angle at about 80 degrees.",
    ],
)
def test_fabricated_camera_analysis_is_blocked(validator, content):
    # The assistant never runs a detector and must not claim to have.
    with pytest.raises(AIResponseError):
        validator.validate_text(content)


@pytest.mark.parametrize(
    "content",
    [
        "This routine guarantees results within four weeks of training.",
        "Doing this will definitely prevent any future back injury.",
    ],
)
def test_unsupported_guarantees_are_blocked(validator, content):
    with pytest.raises(AIResponseError):
        validator.validate_text(content)


def test_safe_discussion_of_pain_is_allowed(validator):
    text = (
        "If you feel sharp pain, stop the exercise and speak to a qualified "
        "physiotherapist before continuing."
    )

    assert validator.validate_text(text) == text


def test_violations_are_reported_by_name(validator):
    violations = validator.safety_violations("I watched your squat depth closely.")

    assert "fabricated analysis" in violations


def test_valid_json_is_parsed(validator):
    payload = {
        "summary": "Good session.",
        "strengths": ["Consistent pace"],
        "improvements": ["Deeper squats"],
        "motivation": "Keep going.",
    }

    parsed = validator.validate_json(
        json.dumps(payload), ("summary", "strengths", "improvements", "motivation")
    )

    assert parsed["summary"] == "Good session."


def test_json_wrapped_in_a_code_fence_is_accepted(validator):
    fenced = '```json\n{"summary": "ok", "strengths": []}\n```'

    parsed = validator.validate_json(fenced, ("summary",))

    assert parsed["summary"] == "ok"


def test_malformed_json_is_rejected(validator):
    with pytest.raises(AIResponseError):
        validator.validate_json("not json at all", ("summary",))


def test_json_missing_a_required_key_is_rejected(validator):
    with pytest.raises(AIResponseError):
        validator.validate_json('{"summary": "ok"}', ("summary", "motivation"))


def test_a_json_array_is_rejected(validator):
    with pytest.raises(AIResponseError):
        validator.validate_json("[1, 2, 3]", ("summary",))


# ---------------------------------------------------------------------------
# Conversation memory
# ---------------------------------------------------------------------------


def test_messages_are_recalled_in_order():
    memory = InMemoryConversationMemory()
    user_id = uuid4()

    memory.append("conv-1", user_id, USER_ROLE, "first")
    memory.append("conv-1", user_id, ASSISTANT_ROLE, "second")

    window = memory.window("conv-1", user_id, limit=10)
    assert [item.content for item in window] == ["first", "second"]


def test_the_window_returns_only_recent_turns():
    memory = InMemoryConversationMemory()
    user_id = uuid4()
    for index in range(20):
        memory.append("conv-1", user_id, USER_ROLE, f"message-{index}")

    window = memory.window("conv-1", user_id, limit=4)

    assert [item.content for item in window] == [
        "message-16",
        "message-17",
        "message-18",
        "message-19",
    ]


def test_conversations_are_isolated_between_users():
    memory = InMemoryConversationMemory()
    alice, bob = uuid4(), uuid4()

    memory.append("shared-id", alice, USER_ROLE, "alice's secret")

    # Bob guesses the conversation identifier and still sees nothing.
    assert memory.window("shared-id", bob, limit=10) == ()


def test_conversations_are_isolated_from_each_other():
    memory = InMemoryConversationMemory()
    user_id = uuid4()

    memory.append("conv-1", user_id, USER_ROLE, "about squats")
    memory.append("conv-2", user_id, USER_ROLE, "about diet")

    assert len(memory.window("conv-1", user_id, limit=10)) == 1


def test_a_conversation_is_capped():
    memory = InMemoryConversationMemory(max_messages=5)
    user_id = uuid4()
    for index in range(12):
        memory.append("conv-1", user_id, USER_ROLE, str(index))

    assert len(memory.window("conv-1", user_id, limit=100)) == 5


def test_the_least_recent_conversation_is_evicted():
    memory = InMemoryConversationMemory(max_conversations=2)
    user_id = uuid4()

    memory.append("conv-1", user_id, USER_ROLE, "one")
    memory.append("conv-2", user_id, USER_ROLE, "two")
    memory.append("conv-3", user_id, USER_ROLE, "three")

    assert memory.conversation_count() == 2
    assert memory.window("conv-1", user_id, limit=10) == ()


def test_a_conversation_can_be_cleared():
    memory = InMemoryConversationMemory()
    user_id = uuid4()
    memory.append("conv-1", user_id, USER_ROLE, "hello")

    memory.clear("conv-1", user_id)

    assert memory.window("conv-1", user_id, limit=10) == ()


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


async def test_an_unconfigured_provider_reports_itself_offline():
    provider = GroqProvider(api_key=None, model="test-model")

    assert provider.is_configured is False
    assert await provider.health_check() is False
    assert provider.model_info().configured is False

    with pytest.raises(AIProviderError):
        await provider.generate(
            ProviderRequest(system_prompt="system", user_prompt="user")
        )


def test_a_provider_payload_is_normalised():
    provider = GroqProvider(api_key="key", model="test-model")

    response = provider._normalise(
        {
            "model": "llama-test",
            "choices": [
                {"message": {"content": "hello"}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
    )

    assert response.content == "hello"
    assert response.provider == "groq"
    assert response.total_tokens == 15


def test_an_unrecognised_provider_payload_is_rejected():
    provider = GroqProvider(api_key="key", model="test-model")

    with pytest.raises(AIProviderError):
        provider._normalise({"unexpected": True})


def test_a_response_without_usage_reports_no_total():
    assert ProviderResponse(content="x", model="m", provider="p").total_tokens is None
