from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from backend.core import logger
from backend.core.apis.schemas.requests.product.product_request import (
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MIN_LATITUDE,
    MIN_LONGITUDE,
)
from backend.core.apis.schemas.responses.error_response import ErrorResponse
from backend.core.apis.schemas.responses.product.heat_response import HeatResponse, MetadataResponse
from backend.core.controllers.product_controller import ProductController

logging = logger(__name__)

router = APIRouter(prefix="/v1", tags=["heat"])

PRODUCT_ERRORS = {
    503: {"model": ErrorResponse, "description": "No heat product is published yet (code `no_product_available`)"},
}


@router.get(
    "/metadata",
    response_model=MetadataResponse,
    summary="Product description",
    description="Freshness of the data, map extent, available layers, level codes, and the honest limits "
                "of the numbers.",
    responses=PRODUCT_ERRORS,
)
def get_metadata(request: Request, response: Response) -> MetadataResponse:
    """
    HTTP GET endpoint describing the published product.

    Args:
        request (Request): Incoming request (gives access to the loaded product).
        response (Response): Response used to set cache headers.

    Returns:
        MetadataResponse: Product description.

    Raises:
        HTTPException: 503 when no product is loaded; 500 for unexpected errors.
    """
    logging.info("Calling GET /v1/metadata endpoint")
    try:
        response.headers["Cache-Control"] = "public, max-age=300"
        return ProductController.get_metadata(request.app.state.store)
    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/metadata endpoint: {httperror}")
        raise httperror
    except Exception as error:
        logging.error(f"Error in GET /v1/metadata endpoint: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error"
        ) from error


@router.get(
    "/heat",
    response_model=HeatResponse,
    summary="Heat at a location",
    description="Surface temperature estimate with a 90% range, the locality and zone, seasonal exposure, and "
                "data age. Coordinates outside Nagpur return 422 with code `outside_study_area`.",
    responses={**PRODUCT_ERRORS, 422: {"model": ErrorResponse, "description": "Invalid or out-of-area coordinates"}},
)
def get_heat(
    request: Request,
    response: Response,
    lat: float = Query(..., ge=MIN_LATITUDE, le=MAX_LATITUDE, description="Latitude (WGS84)", examples=[21.1458]),
    lon: float = Query(..., ge=MIN_LONGITUDE, le=MAX_LONGITUDE, description="Longitude (WGS84)", examples=[79.0882]),
) -> HeatResponse:
    """
    HTTP GET endpoint returning the heat estimate for a point.

    Args:
        request (Request): Incoming request.
        response (Response): Response used to set cache headers.
        lat (float): Latitude.
        lon (float): Longitude.

    Returns:
        HeatResponse: Estimate, range, areas, seasons, and freshness.

    Raises:
        HTTPException: 422 outside the study area; 503 when no product is loaded; 500 for unexpected errors.
    """
    logging.info("Calling GET /v1/heat endpoint")
    try:
        response.headers["Cache-Control"] = "public, max-age=60"
        return ProductController.get_heat(request.app.state.store, lat, lon)
    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/heat endpoint: {httperror}")
        raise httperror
    except Exception as error:
        logging.error(f"Error in GET /v1/heat endpoint: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error"
        ) from error


@router.get(
    "/forecast",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Forecast (not available)",
    description="No forecast model has been validated yet; this endpoint returns 501 until one exists.",
    responses={501: {"model": ErrorResponse, "description": "Forecasting is not available"}},
)
def get_forecast() -> None:
    """
    HTTP GET endpoint reserved for a future forecast model.

    Raises:
        HTTPException: Always 501.
    """
    logging.info("Calling GET /v1/forecast endpoint")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"code": "not_implemented", "message": "Forecasting is not available yet."},
    )
