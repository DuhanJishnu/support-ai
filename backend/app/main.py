"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.mcp_tools import initialize_mcp_client, router as mcp_router
from app.config import settings
from app.exceptions import register_exception_handlers
from app.logging_config import setup_logging
from app.middleware import CorrelationIdMiddleware

# Set up logging immediately
setup_logging(json_format=not settings.DEBUG, log_level="INFO")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        description=(
            "Multi-Agent Customer Support Platform powered by LangGraph and MCP."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Register Correlation ID middleware (outermost)
    application.add_middleware(CorrelationIdMiddleware)

    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Exception Handlers
    register_exception_handlers(application)

    # Include routers
    application.include_router(health_router)
    application.include_router(mcp_router)

    # Startup event to initialize MCP client
    @application.on_event("startup")
    async def startup_event():
        """Initialize MCP client on application startup."""
        await initialize_mcp_client(
            server_urls=settings.mcp_server_urls,
            timeout=settings.MCP_REQUEST_TIMEOUT,
        )

    return application


app = create_app()


@app.get("/")
async def root() -> dict:
    """Root endpoint returning API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
    }


@app.get("/api/trigger-error")
async def trigger_error() -> None:
    """Endpoint to trigger an unhandled Exception for testing purposes."""
    raise ValueError("This is a simulated internal server error.")


@app.get("/api/test-validation")
async def test_validation(value: int) -> dict:
    """Endpoint to trigger a validation error if value is not an integer."""
    return {"value": value}
