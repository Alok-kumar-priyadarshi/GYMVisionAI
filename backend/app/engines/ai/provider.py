# file_name: provider.py

"""LLM provider abstraction.

``docs/08_ai/46_PROVIDER_INTEGRATION.md`` section 5 gives every provider the same
interface, and ``instructions/04_AI_RULES.md`` section 9 requires a provider
change to touch nothing outside this package.

Provider SDKs stay inside their adapter. Nothing above this layer imports Groq.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.shared.exceptions import AIProviderError, AITimeoutError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    """One generation request, per section 7."""

    system_prompt: str
    user_prompt: str
    temperature: float = 0.4
    max_tokens: int = 800
    timeout_seconds: float = 20.0
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """A normalised response, identical in shape for every provider."""

    content: str
    model: str
    provider: str
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int | None:
        """Return the total tokens used, when the provider reports them."""
        if self.prompt_tokens is None or self.completion_tokens is None:
            return None
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """What a provider is currently configured to use."""

    provider: str
    model: str
    configured: bool


class AIProvider(ABC):
    """The interface every language model provider implements."""

    @abstractmethod
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Generate a completion.

        Raises:
            AIProviderError: If the provider is unavailable or rejects the call.
            AITimeoutError: If the provider does not respond in time.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Report whether the provider is reachable and configured."""

    @abstractmethod
    def model_info(self) -> ModelInfo:
        """Return the provider and model in use."""


class GroqProvider(AIProvider):
    """Talks to Groq's OpenAI-compatible chat completions API.

    Implemented with plain HTTP rather than the vendor SDK: the surface used is
    small, and it keeps the dependency list shorter. Either way the detail is
    confined to this class.
    """

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    PROVIDER_NAME = "groq"

    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self._model = model

    @property
    def is_configured(self) -> bool:
        """Report whether an API key is available."""
        return bool(self._api_key)

    def model_info(self) -> ModelInfo:
        return ModelInfo(
            provider=self.PROVIDER_NAME, model=self._model, configured=self.is_configured
        )

    async def health_check(self) -> bool:
        return self.is_configured

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if not self.is_configured:
            logger.error("GROQ_API_KEY is not configured; the assistant is offline.")
            raise AIProviderError()

        import httpx

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(
                    self.BASE_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
        except (httpx.TimeoutException, asyncio.TimeoutError) as error:
            logger.warning("AI provider timed out.")
            raise AITimeoutError() from error
        except httpx.HTTPError as error:
            logger.warning("AI provider request failed.")
            raise AIProviderError() from error

        if response.status_code >= 400:
            # The provider's message may echo the prompt, so it is never shown.
            logger.error("AI provider returned status %d.", response.status_code)
            raise AIProviderError()

        return self._normalise(response.json())

    def _normalise(self, body: dict[str, Any]) -> ProviderResponse:
        """Convert a provider payload into the shared response shape."""
        try:
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            logger.error("AI provider returned an unrecognised payload.")
            raise AIProviderError() from error

        usage = body.get("usage") or {}
        return ProviderResponse(
            content=content or "",
            model=body.get("model", self._model),
            provider=self.PROVIDER_NAME,
            finish_reason=choice.get("finish_reason"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
