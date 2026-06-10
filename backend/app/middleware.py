"""ASGI middleware components for the FastAPI application."""

import uuid
from typing import Any

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send


class CorrelationIdMiddleware:
    """ASGI Middleware that manages a unique correlation ID per request.

    It extracts the ID from request headers (if provided) or generates a new one.
    It binds it to the structlog context and adds it to response headers.
    """

    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID"):
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process ASGI request/response."""
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Attempt to read correlation ID from request headers
        correlation_id = None
        for key, value in scope.get("headers", []):
            if key.decode("latin1").lower() == self.header_name.lower():
                correlation_id = value.decode("latin1")
                break

        # Generate a new unique ID if not present in request headers
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Reset context variables for task isolation
        structlog.contextvars.clear_contextvars()
        # Bind the correlation ID to structlog context
        structlog.contextvars.bind_contextvars(request_id=correlation_id)

        # Wrap Send to inject the correlation ID into the response headers
        async def send_wrapper(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                header_bytes_key = self.header_name.lower().encode("latin1")
                header_bytes_value = correlation_id.encode("latin1")

                # Update header if already set, else append it
                header_found = False
                for idx, (k, _v) in enumerate(headers):
                    if k.lower() == header_bytes_key:
                        headers[idx] = (k, header_bytes_value)
                        header_found = True
                        break

                if not header_found:
                    headers.append((header_bytes_key, header_bytes_value))

                message["headers"] = headers

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Clear context variables when request ends to prevent context pollution
            structlog.contextvars.clear_contextvars()
