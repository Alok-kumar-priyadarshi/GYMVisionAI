# file_name: response_validator.py

"""Response validation and safety guardrails.

``instructions/04_AI_RULES.md`` section 8 requires every response to be validated
before it is returned, and ``prompts/08_SAFETY_GUARDRAILS.md`` section 3 places
the guardrails last in the pipeline, after the provider and before the frontend.

Validation covers what a machine can reliably check: emptiness, truncation,
structure, and claims the assistant is documented never to make. It is a
backstop for the system prompt, not a replacement for it.
"""

import json
import logging
import re
from dataclasses import dataclass, field

from app.shared.exceptions import AIResponseError

logger = logging.getLogger(__name__)

MIN_RESPONSE_CHARACTERS = 12
MAX_RESPONSE_CHARACTERS = 8_000

MEDICAL_CLAIM_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\byou (?:have|are suffering from|are diagnosed with)\b", re.I),
    re.compile(r"\b(?:i diagnose|my diagnosis|prescribe|prescription)\b", re.I),
    re.compile(r"\btake \d+\s?(?:mg|ml|tablets?|pills?)\b", re.I),
)
"""Phrasing that would amount to diagnosis or prescription.

``prompts/08_SAFETY_GUARDRAILS.md`` section 5 forbids both outright.
"""

FABRICATED_ANALYSIS_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\bI (?:watched|saw|observed|analysed|analyzed) (?:you|your)\b", re.I),
    re.compile(r"\b(?:from|in) the video I\b", re.I),
    re.compile(r"\bI (?:measured|detected|tracked) your\b", re.I),
)
"""Claims to have performed camera analysis.

The AI never runs a detector. ``docs/08_ai/41_AI_ARCHITECTURE.md`` section 13
forbids pretending detector analysis occurred.
"""

GUARANTEE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\bguarantee[sd]?\b.{0,40}\b(?:result|weight|injury|outcome)", re.I),
    re.compile(r"\b(?:will|is) (?:definitely|certainly) (?:cure|heal|prevent)\b", re.I),
)
"""Unsupported guarantees, forbidden by sections 5 and 6 of the guardrails."""

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """The outcome of validating one response."""

    content: str
    safe: bool = True
    violations: tuple[str, ...] = field(default=())


class ResponseValidator:
    """Checks an AI response before it reaches a user."""

    def validate_text(self, content: str) -> str:
        """Validate a conversational response.

        Args:
            content: The provider's raw output.

        Returns:
            The cleaned response.

        Raises:
            AIResponseError: If the response is empty, oversized, or breaches a
                documented safety rule.
        """
        cleaned = (content or "").strip()

        if len(cleaned) < MIN_RESPONSE_CHARACTERS:
            logger.warning("AI response rejected: empty or too short.")
            raise AIResponseError()

        if len(cleaned) > MAX_RESPONSE_CHARACTERS:
            logger.warning("AI response rejected: exceeded the maximum length.")
            raise AIResponseError()

        violations = self.safety_violations(cleaned)
        if violations:
            # The offending text is never logged; it may quote user context.
            logger.warning("AI response rejected: %s.", ", ".join(violations))
            raise AIResponseError()

        return cleaned

    def validate_json(self, content: str, required_keys: tuple[str, ...]) -> dict:
        """Validate a response that must be a JSON object.

        Models frequently wrap JSON in a code fence despite instructions, so the
        fence is stripped before parsing rather than treated as a failure.

        Raises:
            AIResponseError: If the response is not a JSON object with the
                required keys, or breaches a safety rule.
        """
        cleaned = _CODE_FENCE.sub("", (content or "").strip()).strip()

        violations = self.safety_violations(cleaned)
        if violations:
            logger.warning("AI response rejected: %s.", ", ".join(violations))
            raise AIResponseError()

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as error:
            logger.warning("AI response rejected: not valid JSON.")
            raise AIResponseError() from error

        if not isinstance(payload, dict):
            logger.warning("AI response rejected: JSON was not an object.")
            raise AIResponseError()

        missing = [key for key in required_keys if key not in payload]
        if missing:
            logger.warning("AI response rejected: missing keys.")
            raise AIResponseError()

        return payload

    @staticmethod
    def safety_violations(content: str) -> tuple[str, ...]:
        """Return the names of any safety rules the text breaches."""
        found: list[str] = []

        checks = (
            ("medical claim", MEDICAL_CLAIM_PATTERNS),
            ("fabricated analysis", FABRICATED_ANALYSIS_PATTERNS),
            ("unsupported guarantee", GUARANTEE_PATTERNS),
        )
        for name, patterns in checks:
            if any(pattern.search(content) for pattern in patterns):
                found.append(name)

        return tuple(found)
