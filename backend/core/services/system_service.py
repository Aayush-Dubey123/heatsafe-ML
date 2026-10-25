import platform
from typing import Dict, Any
from backend.core import logger

logging = logger(__name__)


class SystemService:
    """
    Service layer providing hardware telemetry, host operating environment,
    and diagnostic information for the HeatSafe-ML runtime.
    """

    @staticmethod
    def get_system_telemetry() -> Dict[str, Any]:
        """
        Gather host runtime operating system and interpreter platform metrics.

        Returns:
            Dict[str, Any]: Telemetry map including Python version, platform, architecture.

        Raises:
            None
        """
        logging.info("Executing SystemService.get_system_telemetry")
        try:
            telemetry = {
                "os": platform.system(),
                "release": platform.release(),
                "architecture": platform.machine(),
                "python_version": platform.python_version(),
            }
            return telemetry
        except Exception as err:
            logging.error(f"Error in SystemService.get_system_telemetry: {err}")
            return {"error": "telemetry_unavailable"}
