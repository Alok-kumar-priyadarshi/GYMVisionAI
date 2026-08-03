# file_name: middleware.py

"""Request correlation and access logging.

``docs/11_monitoring/49_MONITORING_ARCHITECTURE.md`` section 11 requires every
request to carry a request identifier, and
``docs/04_backend/27_API_DESIGN_GUIDELINES.md`` section 21 requires logging the
method, route, status code and response time while never logging tokens.

Section 16 of the monitoring architecture requires monitoring never to interrupt
the application, so this middleware adds no failure path of its own.
"""

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import REQUEST_ID_HEADER, set_request_id

logger = logging.getLogger(__name__)

MAX_REQUEST_ID_LENGTH = 128


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request identifier and logs the outcome of every request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = self._resolve_request_id(request)
        set_request_id(request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # The exception handlers produce the response; record the timing and
            # let the exception continue to them.
            self._log(request, status_code=500, started=started)
            set_request_id(None)
            raise

        self._log(request, status_code=response.status_code, started=started)
        response.headers[REQUEST_ID_HEADER] = request_id
        set_request_id(None)
        return response

    @staticmethod
    def _resolve_request_id(request: Request) -> str:
        """Reuse a caller-supplied identifier, or generate one.

        A caller-supplied value is length-limited so an oversized header cannot
        bloat every log line it appears in.
        """
        supplied = request.headers.get(REQUEST_ID_HEADER, "").strip()
        if supplied:
            return supplied[:MAX_REQUEST_ID_LENGTH]
        return uuid4().hex

    @staticmethod
    def _log(request: Request, status_code: int, started: float) -> None:
        """Record one access log entry.

        The route template is logged rather than the raw path, so identifiers in
        the URL do not spread through the logs. Query strings and headers are
        never logged, because they may carry tokens.
        """
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)

        logger.info(
            "%s %s %d",
            request.method,
            path,
            status_code,
            extra={
                "http_method": request.method,
                "http_route": path,
                "http_status": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
