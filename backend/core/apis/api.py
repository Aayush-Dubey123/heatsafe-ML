from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.core import logger
from backend.core.apis.middleware import REQUEST_ID_HEADER, RequestContextMiddleware, register_error_handlers
from backend.core.apis.routes.health import router as health_router
from backend.core.apis.schemas.responses.error_response import ErrorResponse
from backend.core.config.settings import get_settings
from backend.core.database.database import engine

logging = logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage lifecycle events during application startup and shutdown.

    Verifies database reachability on startup; schema changes are applied
    only through Alembic migrations, never created implicitly here.

    Args:
        app (FastAPI): Instantiated FastAPI application.

    Yields:
        None: Yields control to running application until SIGTERM/SIGINT.
    """
    logging.info("Executing application lifespan startup: verifying database connectivity")
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logging.info("Database reachable; schema is managed by Alembic migrations")
    except Exception as error:
        logging.warning(f"Database not reachable at startup; /health will report it: {type(error).__name__}")
    yield
    logging.info("Executing application lifespan shutdown: releasing resources")
    engine.dispose()


def create_app() -> FastAPI:
    """
    Factory constructing and configuring the unified FastAPI ASGI application.

    Configures CORS from settings, request-ID and security-header middleware,
    uniform error handlers, lifespan handler, and route mounts.

    Returns:
        FastAPI: Configured ASGI application instance.
    """
    settings = get_settings()
    application = FastAPI(
        title="HeatSafe-ML Backend API",
        description="Geospatial Machine Learning & Heat Exposure Analytics API for Nagpur, India",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        responses={
            422: {"model": ErrorResponse, "description": "Request validation failed"},
            500: {"model": ErrorResponse, "description": "Internal server error"},
        },
    )

    # Public, read-only API: no cookies, so credentials stay disabled.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    application.add_middleware(
        RequestContextMiddleware,
        enable_hsts=settings.environment == "production",
    )
    register_error_handlers(application)

    # Mount domain routes
    application.include_router(health_router, prefix="/api")

    logging.info(f"FastAPI application constructed for environment '{settings.environment}'")
    return application


# Global ASGI application instance
app = create_app()
