# file_name: response.py

"""Standard API response envelopes.

Defined by ``contracts/common/02_RESPONSE_FORMAT.md``. Every endpoint returns one
of these shapes, so a client can deserialise any response consistently.

Success:

```json
{"success": true, "message": "...", "data": {}}
```

Failure:

```json
{"success": false, "error": {"code": "AUTH-001", "message": "..."}}
```

``docs/04_backend/27_API_DESIGN_GUIDELINES.md`` section 8 shows a different error
envelope, carrying a top-level ``message`` and an ``error.details`` array with an
undocumented ``INVALID_INPUT`` code. The contract shape above is implemented
instead: ``COMMON-001`` permits documented error codes only, and every endpoint
contract uses the contract shape.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class SuccessResponse(BaseModel, Generic[DataT]):
    """Envelope returned by every successful request."""

    model_config = ConfigDict(frozen=True)

    success: bool = True
    message: str = Field(min_length=1)
    data: DataT | None = None


class ErrorDetail(BaseModel):
    """The error body carried by a failed request."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ErrorResponse(BaseModel):
    """Envelope returned by every failed request."""

    model_config = ConfigDict(frozen=True)

    success: bool = False
    error: ErrorDetail


def success(message: str, data: Any = None) -> dict[str, Any]:
    """Build a success payload.

    Args:
        message: Human-readable description of what happened.
        data: The resource being returned, or ``None`` for empty responses.

    Returns:
        A JSON-serialisable success envelope.
    """
    return {"success": True, "message": message, "data": data}


def failure(code: str, message: str) -> dict[str, Any]:
    """Build an error payload.

    Args:
        code: A documented error code from ``COMMON-001``.
        message: Human-readable, safe to show a user.

    Returns:
        A JSON-serialisable error envelope.
    """
    return {"success": False, "error": {"code": code, "message": message}}
