from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.core import logger
from backend.core.database.database import get_db
from backend.core.controllers.health_controller import HealthController
from backend.core.apis.schemas.requests.health_request import HealthPingRequest
from backend.core.apis.schemas.responses.health_response import HealthResponse

logging = logger(__name__)

router = APIRouter(prefix="/v1", tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Health Check",
    description="Evaluate operational availability and verify database connectivity.",
)
def get_health_status(db: Session = Depends(get_db)) -> HealthResponse:
    """
    HTTP GET endpoint evaluating service and database heartbeat status.

    Args:
        db (Session): Injected database session dependency.

    Returns:
        HealthResponse: Health status payload including version and timestamp.

    Raises:
        HTTPException: Propagates controller HTTPException or converts unhandled error to 500.
    """
    logging.info("Calling GET /v1/health endpoint")
    try:
        return HealthController.evaluate_health(db=db)
    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/health endpoint: {httperror}")
        raise httperror
    except Exception as error:
        logging.error(f"Error in GET /v1/health endpoint: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error during health verification",
        )


@router.post(
    "/health/ping",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Diagnostic Ping",
    description="Validate end-to-end transport schema serialization with client diagnostic echo.",
)
def ping_service(
    payload: HealthPingRequest,
    db: Session = Depends(get_db),
) -> HealthResponse:
    """
    HTTP POST diagnostic ping echoing test payload and verifying persistence.

    Args:
        payload (HealthPingRequest): Inbound client ping diagnostic parameters.
        db (Session): Injected database session dependency.

    Returns:
        HealthResponse: Health response with echoed test content.

    Raises:
        HTTPException: Propagates controller HTTPException or converts unhandled error to 500.
    """
    logging.info("Calling POST /v1/health/ping endpoint")
    try:
        return HealthController.evaluate_health(db=db, request_payload=payload)
    except HTTPException as httperror:
        logging.error(f"Error in POST /v1/health/ping endpoint: {httperror}")
        raise httperror
    except Exception as error:
        logging.error(f"Error in POST /v1/health/ping endpoint: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error during diagnostic ping",
        )
