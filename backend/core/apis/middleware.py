import re
import uuid
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.commons.logger import request_id_ctx
from backend.core import logger
from backend.core.apis.schemas.responses.error_response import ErrorBody, ErrorResponse

logging = logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
_API_CSP = "default-src 'none'; frame-ancestors 'none'"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Assign a correlation ID to every request and add security headers.

    Reuses a well-formed inbound X-Request-ID, otherwise generates a UUID4,
    exposes it to the logger, and returns it on the response.
    """

    def __init__(self, app: Any, enable_hsts: bool = False) -> None:
        """
        Configure the middleware.

        HSTS is only sent when the API is served over HTTPS in production.

        Args:
            app (Any): Downstream ASGI application.
            enable_hsts (bool): Whether to emit Strict-Transport-Security.
        """
        super().__init__(app)
        self.enable_hsts = enable_hsts

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """
        Bind the request ID, run the request, and decorate the response.

        Args:
            request (Request): Inbound HTTP request.
            call_next (Callable): Next handler in the ASGI chain.

        Returns:
            Response: Downstream response with request ID and security headers.
        """
        inbound = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = inbound if _VALID_REQUEST_ID.match(inbound) else str(uuid.uuid4())
        request.state.request_id = request_id
        token = request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)

        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if not request.url.path.startswith(_DOCS_PATHS):
            response.headers["Content-Security-Policy"] = _API_CSP
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


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
    message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    return _error_response(
        request,
        exc.status_code,
        _status_code_name(exc.status_code),
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
