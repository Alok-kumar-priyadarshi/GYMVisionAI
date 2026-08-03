# file_name: logging_config.py

"""Structured logging and request correlation.

``docs/11_monitoring/49_MONITORING_ARCHITECTURE.md`` section 5 requires
structured logs, section 11 requires every request to carry a request identifier
that propagates through the whole stack, and section 18 forbids logging secrets
or tokens.

The request identifier lives in a context variable so any module can log it
without threading it through call signatures. Business engines therefore stay
free of monitoring concerns.
"""

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

from app.core.config import LogLevel, Settings

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

_RESERVED_RECORD_FIELDS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"asctime", "message", "taskName"}


def set_request_id(request_id: str | None) -> None:
    """Bind a request identifier to the current context."""
    _request_id.set(request_id)


def get_request_id() -> str | None:
    """Return the request identifier bound to the current context."""
    return _request_id.get()


class RequestIdFilter(logging.Filter):
    """Attaches the current request identifier to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """Renders log records as single-line JSON for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_FIELDS and key != "request_id":
                payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    """Install the application's logging configuration.

    Args:
        settings: The loaded application settings.

    Logging is configured once at startup. Handlers are replaced rather than
    appended, so repeated calls in tests do not duplicate output.
    """
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.addFilter(RequestIdFilter())

    if settings.json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.value)

    # Uvicorn installs its own handlers; route them through ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True

    if settings.log_level is not LogLevel.DEBUG:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
