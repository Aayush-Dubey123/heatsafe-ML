import uvicorn

from backend.core import logger
from backend.core.apis.api import app  # noqa: F401 - imported so configuration errors fail fast
from backend.core.config.settings import get_settings

logging = logger(__name__)


def run_server() -> None:
    """
    Launch the ASGI application using Uvicorn with validated settings.

    Host and port come from HEATSAFE_HOST / HEATSAFE_PORT (default 127.0.0.1:8000);
    containers set HEATSAFE_HOST=0.0.0.0 explicitly.

    Returns:
        None
    """
    settings = get_settings()
    logging.info(f"Starting HeatSafe-ML Backend server on {settings.host}:{settings.port}")
    uvicorn.run("backend.core.apis.api:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run_server()
