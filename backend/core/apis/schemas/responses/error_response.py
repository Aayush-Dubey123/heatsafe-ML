from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """
    Machine- and human-readable description of a failed request.

    Attributes:
        code (str): Stable snake_case error code clients can branch on.
        message (str): Safe, human-readable summary (never a stack trace).
        details (list[dict[str, Any]] | None): Optional field-level problems.
        request_id (str): Correlation ID echoed in the X-Request-ID header.
    """

    code: str = Field(description="Stable snake_case error code, e.g. 'validation_error'.")
    message: str = Field(description="Safe human-readable summary of the error.")
    details: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional field-level problems (location, message, type).",
    )
    request_id: str = Field(description="Correlation ID matching the X-Request-ID response header.")


class ErrorResponse(BaseModel):
    """
    Uniform error envelope returned by every endpoint (Decision T15).

    Attributes:
        error (ErrorBody): The error description.
    """

    error: ErrorBody
