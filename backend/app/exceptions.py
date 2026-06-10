"""Custom exception handlers returning uniform JSON error responses."""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger()


def create_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    """Create a uniform JSON response with the active correlation ID."""
    correlation_id = structlog.contextvars.get_contextvars().get("request_id")

    content = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
        },
        "correlation_id": correlation_id,
    }
    if details is not None:
        content["error"]["details"] = details  # type: ignore

    return JSONResponse(status_code=status_code, content=content)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle standard Starlette/FastAPI HTTPExceptions."""
    logger.warning(
        "HTTP exception occurred",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method,
    )

    headers = getattr(exc, "headers", None)
    response = create_error_response(
        status_code=exc.status_code,
        error_code=f"HTTP_{exc.status_code}",
        message=str(exc.detail),
    )
    if headers:
        for key, value in headers.items():
            response.headers[key] = value
    return response


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors from Pydantic models/Request parameters."""
    errors = exc.errors()
    logger.warning(
        "Validation error occurred",
        path=request.url.path,
        method=request.method,
        errors=errors,
    )

    return create_error_response(
        status_code=422,
        error_code="VALIDATION_ERROR",
        message="Request input validation failed.",
        details=errors,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general unhandled python exceptions (HTTP 500)."""
    logger.exception(
        "Unhandled server exception occurred",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )

    return create_error_response(
        status_code=500,
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register standard handlers for HTTP, Validation, and General exceptions."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore
    app.add_exception_handler(Exception, unhandled_exception_handler)
