import os
import uvicorn
from backend.core import logger
from backend.core.apis.api import app

logging = logger(__name__)


def run_server() -> None:
    """
    Launch the ASGI application using Uvicorn with runtime environment variables.

    Slices host and port configurations from environment, defaulting to 0.0.0.0:8000.

    Returns:
        None

    Raises:
        None
    """
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    logging.info(f"Starting HeatSafe-ML Backend server on {host}:{port}")
    uvicorn.run("backend.core.apis.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run_server()
