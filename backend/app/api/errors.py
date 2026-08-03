# file_name: errors.py

"""Translation of exceptions into standard API error responses.

``instructions/01_CODING_RULES.md`` section 9 places this translation at the API
layer, so business engines raise domain exceptions and never know about HTTP.

``contracts/common/02_RESPONSE_FORMAT.md`` section 11 forbids returning stack
traces or HTML error pages, and
``docs/09_security/47_SECURITY_ARCHITECTURE.md`` section 19 requires generic
messages that do not leak implementation details. Unexpected failures are
therefore logged in full and reported as a bare system error.
"""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.response import failure
from app.shared.exceptions import GymVisionError

logger = logging.getLogger(__name__)

STATUS_TO_ERROR_CODE: dict[int, tuple[str, str]] = {
    401: ("AUTH-001", "Authentication required."),
    403: ("AUTH-005", "Access denied."),
    404: ("SYSTEM-001", "The requested resource was not found."),
    405: ("VALIDATION-004", "Unsupported parameter."),
    409: ("EXERCISE-004", "Invalid exercise state."),
    422: ("VALIDATION-003", "Invalid field value."),
    429: ("SYSTEM-003", "Service temporarily unavailable."),
}
"""Error codes for failures raised by the framework rather than by an engine.

``COMMON-001`` lists 429 in its status table but defines no rate-limit code, so
the generic temporarily-unavailable code is used until one exists.
"""

FALLBACK_ERROR = ("SYSTEM-001", "Internal server error.")


async def handle_gymvision_error(
    request: Request, exception: GymVisionError
) -> JSONResponse:
    """Return the documented response for a known application error."""
    if exception.http_status >= 500:
        logger.error(
            "Request failed: %s", exception.error_code, exc_info=exception
        )
    else:
        logger.info("Request rejected: %s", exception.error_code)

    return JSONResponse(
        status_code=exception.http_status,
        content=failure(exception.error_code, exception.message),
    )


async def handle_validation_error(
    request: Request, exception: RequestValidationError
) -> JSONResponse:
    """Return a validation failure for a malformed request.

    ``27_API_DESIGN_GUIDELINES.md`` section 14 requires 422 for invalid requests.
    Field names are reported so a client can correct the request, but submitted
    values are not echoed back.
    """
    fields = sorted(
        {
            ".".join(str(part) for part in error["loc"][1:]) or "body"
            for error in exception.errors()
        }
    )
    detail = "Invalid value for: " + ", ".join(fields) if fields else "Invalid request."

    logger.info("Request validation failed.")
    return JSONResponse(status_code=422, content=failure("VALIDATION-003", detail))


async def handle_http_exception(
    request: Request, exception: StarletteHTTPException
) -> JSONResponse:
    """Return the documented response for a framework-raised HTTP error."""
    code, default_message = STATUS_TO_ERROR_CODE.get(
        exception.status_code, FALLBACK_ERROR
    )

    return JSONResponse(
        status_code=exception.status_code,
        content=failure(code, _message_for(exception, default_message)),
    )


def _message_for(exception: StarletteHTTPException, default_message: str) -> str:
    """Return the most useful message for an HTTP error.

    Starlette defaults ``detail`` to the bare HTTP reason phrase, such as
    ``"Not Found"``. That is replaced with the documented message. A detail set
    deliberately by application code is kept.
    """
    detail = exception.detail
    if not isinstance(detail, str) or not detail.strip():
        return default_message

    try:
        reason_phrase = HTTPStatus(exception.status_code).phrase
    except ValueError:
        return detail

    return default_message if detail == reason_phrase else detail


async def handle_unexpected_error(
    request: Request, exception: Exception
) -> JSONResponse:
    """Return a generic system error and log the cause in full."""
    logger.exception("Unhandled exception while processing a request.")

    code, message = FALLBACK_ERROR
    return JSONResponse(status_code=500, content=failure(code, message))


def register_exception_handlers(application: FastAPI) -> None:
    """Attach every exception handler to the application."""
    application.add_exception_handler(GymVisionError, handle_gymvision_error)
    application.add_exception_handler(RequestValidationError, handle_validation_error)
    application.add_exception_handler(StarletteHTTPException, handle_http_exception)
    application.add_exception_handler(Exception, handle_unexpected_error)
