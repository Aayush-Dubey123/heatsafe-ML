from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core import logger
from backend.core.database.base_class import Base
from backend.core.database.database import engine
from backend.core.apis.routes.health import router as health_router

logging = logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage lifecycle events during application startup and shutdown.

    Creates initial database schema tables on startup and logs status.

    Args:
        app (FastAPI): Instantiated FastAPI application.

    Yields:
        None: Yields control to running application until SIGTERM/SIGINT.
    """
    logging.info("Executing application lifespan startup: initializing database schema")
    Base.metadata.create_all(bind=engine)
    logging.info("Database tables verified successfully")
    yield
    logging.info("Executing application lifespan shutdown: releasing resources")


def create_app() -> FastAPI:
    """
    Factory constructing and configuring the unified FastAPI ASGI application.

    Configures CORS, middleware, OpenAPI tags, lifespan handler, and route mounts.

    Returns:
        FastAPI: Configured ASGI application instance.

    Raises:
        None
    """
    application = FastAPI(
        title="HeatSafe-ML Backend API",
        description="Geospatial Machine Learning & Heat Exposure Analytics API for Nagpur, India",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Security: restrict CORS origins in production; permissive during development
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount domain routes
    application.include_router(health_router, prefix="/api")

    logging.info("FastAPI application instance constructed and routers mounted")
    return application


# Global ASGI application instance
app = create_app()
