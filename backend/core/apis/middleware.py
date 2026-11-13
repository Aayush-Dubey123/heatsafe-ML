import re
import time
import uuid
from collections import OrderedDict, deque
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.commons.logger import request_id_ctx
from backend.core import logger
from backend.core.apis.schemas.responses.error_response import ErrorBody, ErrorResponse

logging = logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
_API_CSP = "default-src 'none'; frame-ancestors 'none'"


class RequestContextMiddleware:
    """
    Assign a correlation ID to every request and add security headers.

    Written as plain ASGI middleware (much cheaper than Starlette's BaseHTTPMiddleware).
    Reuses a well-formed inbound X-Request-ID, otherwise generates a UUID4, exposes it to
    the logger, and returns it on the response.
    """

    def __init__(self, app: ASGIApp, enable_hsts: bool = False) -> None:
        """
        Configure the middleware.

        HSTS is only sent when the API is served over HTTPS in production.

        Args:
            app (ASGIApp): Downstream ASGI application.
            enable_hsts (bool): Whether to emit Strict-Transport-Security.
        """
        self.app = app
        self.enable_hsts = enable_hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Bind the request ID, run the request, and decorate the response headers.

        Args:
            scope (Scope): ASGI connection scope.
            receive (Receive): ASGI receive channel.
            send (Send): ASGI send channel.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        inbound = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
        request_id = inbound if _VALID_REQUEST_ID.match(inbound) else str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        is_docs = str(scope["path"]).startswith(_DOCS_PATHS)
        token = request_id_ctx.set(request_id)

        async def send_with_headers(message: Message) -> None:
            """
            Add the correlation ID and security headers to the response start message.
            """
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                if not is_docs:
                    headers["Content-Security-Policy"] = _API_CSP
                if self.enable_hsts:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            request_id_ctx.reset(token)


class RateLimitMiddleware:
    """
    In-process sliding-window rate limiter per client (Decision T12: single instance, no Redis).

    Map tiles and documentation pages are exempt because a map view legitimately loads many tiles.
    The client key is the first X-Forwarded-For entry when present (hosting proxies), else the socket address.
    """

    EXEMPT_PREFIXES = ("/api/v1/tiles/", "/docs", "/redoc", "/openapi.json")
    MAX_CLIENTS = 10_000
    WINDOW_SECONDS = 60.0

    def __init__(self, app: ASGIApp, limit_per_minute: int) -> None:
        """
        Configure the limiter.

        Args:
            app (ASGIApp): Downstream ASGI application.
            limit_per_minute (int): Allowed requests per client per minute.
        """
        self.app = app
        self.limit = limit_per_minute
        self.hits: OrderedDict[str, deque[float]] = OrderedDict()

    def _retry_after(self, client: str) -> int | None:
        """
        Record a hit for a client and report how long it must wait if over quota.

        Args:
            client (str): Client key.

        Returns:
            int | None: Seconds to wait, or None when the request is allowed.
        """
        now = time.monotonic()
        window = self.hits.pop(client, deque())
        while window and now - window[0] > self.WINDOW_SECONDS:
            window.popleft()
        if len(window) >= self.limit:
            self.hits[client] = window
            return max(1, int(self.WINDOW_SECONDS - (now - window[0])))
        window.append(now)
        self.hits[client] = window
        while len(self.hits) > self.MAX_CLIENTS:
            self.hits.popitem(last=False)
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Reject the request with 429 when the client exceeded its quota.

        Args:
            scope (Scope): ASGI connection scope.
            receive (Receive): ASGI receive channel.
            send (Send): ASGI send channel.
        """
        if scope["type"] != "http" or str(scope["path"]).startswith(self.EXEMPT_PREFIXES):
            await self.app(scope, receive, send)
            return
        forwarded = Headers(scope=scope).get("x-forwarded-for", "").split(",")[0].strip()
        client_info = scope.get("client")
        client = forwarded or (client_info[0] if client_info else "unknown")
        retry_after = self._retry_after(client)
        if retry_after is None:
            await self.app(scope, receive, send)
            return
        logging.warning("Rate limit exceeded for a client")
        response = _error_response(Request(scope), status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited",
                                   "Too many requests. Wait a moment and try again.",
                                   headers={"Retry-After": str(retry_after)})
        await response(scope, receive, send)


def _request_id(request: Request) -> str:
    """
    Read the correlation ID assigned by RequestContextMiddleware.

    Falls back to "-" if the middleware did not run (should not happen in the app).

    Args:
        request (Request): Current HTTP request.

    Returns:
        str: The request's correlation ID.
    """
    return getattr(request.state, "request_id", "-")


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """
    Serialize an error into the uniform envelope.

    Args:
        request (Request): Current HTTP request.
        status_code (int): HTTP status to return.
        code (str): Stable snake_case error code.
        message (str): Safe human-readable message.
        details (list[dict[str, Any]] | None): Optional field-level problems.
        headers (dict[str, str] | None): Extra response headers to preserve.

    Returns:
        JSONResponse: Response carrying an ErrorResponse body.
    """
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details, request_id=_request_id(request))
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


def _status_code_name(status_code: int) -> str:
    """
    Convert an HTTP status into a snake_case error code.

    Args:
        status_code (int): HTTP status, e.g. 404.

    Returns:
        str: Code such as 'not_found', or 'http_error' for unknown statuses.
    """
    try:
        return HTTPStatus(status_code).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return "http_error"


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Wrap HTTPExceptions raised by routes and controllers in the error envelope.

    Keeps meaningful 4xx/5xx statuses; non-string details are replaced by the status phrase.

    Args:
        request (Request): Current HTTP request.
        exc (Exception): The raised Starlette/FastAPI HTTPException.

    Returns:
        JSONResponse: Error envelope with the original status code.
    """
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101 - handler is registered for this type only
    code = _status_code_name(exc.status_code)
    detail = exc.detail
    if isinstance(detail, dict) and isinstance(detail.get("code"), str) and isinstance(detail.get("message"), str):
        code, message = detail["code"], detail["message"]  # stable, documented error code chosen by the caller
    else:
        message = detail if isinstance(detail, str) else HTTPStatus(exc.status_code).phrase
    return _error_response(
        request,
        exc.status_code,
        code,
        message,
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Convert request validation failures into a 422 error envelope.

    Only location, message, and type are returned; raw input values are never echoed.

    Args:
        request (Request): Current HTTP request.
        exc (Exception): The raised RequestValidationError.

    Returns:
        JSONResponse: 422 error envelope with field-level details.
    """
    assert isinstance(exc, RequestValidationError)  # noqa: S101 - handler is registered for this type only
    logging.warning(f"Request validation failed on {request.method} {request.url.path}")
    details = [
        {"loc": list(err.get("loc", ())), "msg": str(err.get("msg", "")), "type": str(err.get("type", ""))}
        for err in exc.errors()
    ]
    return _error_response(
        request,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        "Request validation failed.",
        details=details,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Last-resort handler that hides internal errors behind a generic 500.

    The exception is logged with the request ID; nothing internal reaches the client.

    Args:
        request (Request): Current HTTP request.
        exc (Exception): Any uncaught exception.

    Returns:
        JSONResponse: Generic 500 error envelope.
    """
    logging.error(
        f"Error in {request.method} {request.url.path} "
        f"(request_id={_request_id(request)}): {type(exc).__name__}: {exc}"
    )
    return _error_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_server_error",
        "Internal Server Error",
    )


def register_error_handlers(app: FastAPI) -> None:
    """
    Attach the uniform error-envelope handlers to the application.

    Args:
        app (FastAPI): Application being configured.
    """
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
