from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend.core import logger
from backend.core.cruds.health_crud import HealthCRUD
from backend.core.models.health_model import ServiceStatus
from backend.core.apis.schemas.responses.health_response import HealthResponse
from backend.core.apis.schemas.requests.health_request import HealthPingRequest

logging = logger(__name__)


class HealthController:
    """
    Controller orchestrating system heartbeat evaluation and persistence audit.
    """

    @staticmethod
    def evaluate_health(
        db: Session,
        request_payload: Optional[HealthPingRequest] = None,
    ) -> HealthResponse:
        """
        Evaluate and certify operational health of the backend API and persistence layer.

        Args:
            db (Session): Active database session.
            request_payload (Optional[HealthPingRequest]): Inbound client ping diagnostic parameters.

        Returns:
            HealthResponse: Verified health contract ready for API serialization.

        Raises:
            HTTPException 503: If database heartbeat persistence or audit fails.
        """
        logging.info("Executing HealthController.evaluate_health")
        try:
            # Audit persistence engine by writing and confirming heartbeat
            HealthCRUD.record_heartbeat(
                db=db,
                service_name="heatsafe-backend",
                status=ServiceStatus.HEALTHY,
            )
            db_status = "connected"
        except Exception as err:
            logging.error(f"Error in HealthController.evaluate_health persistence check: {err}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connectivity check failed",
            )

        echo_val = request_payload.echo_message if request_payload else None

        return HealthResponse(
            status=ServiceStatus.HEALTHY.value,
            service="heatsafe-backend",
            version="0.1.0",
            timestamp=datetime.now(timezone.utc),
            database=db_status,
            echo=echo_val,
        )
