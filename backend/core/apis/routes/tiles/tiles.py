from fastapi import APIRouter, HTTPException, Path, Request, Response, status
from fastapi.responses import FileResponse

from backend.core import logger
from backend.core.apis.schemas.requests.product.product_request import Season, TileLayer
from backend.core.apis.schemas.responses.error_response import ErrorResponse
from backend.core.apis.schemas.responses.product.heat_response import GeoJSONFeatureCollection
from backend.core.controllers.product_controller import ProductController

logging = logger(__name__)

router = APIRouter(prefix="/v1", tags=["map"])


@router.get(
    "/tiles/{layer}/{z}/{x}/{y}.png",
    response_class=FileResponse,
    summary="Map tile",
    description="Pre-rendered PNG map tile (Web Mercator, standard XYZ). Layer ids come from /metadata.",
    responses={200: {"content": {"image/png": {}}, "description": "PNG tile"},
               404: {"model": ErrorResponse, "description": "No tile here (outside the study area or no data)"},
               503: {"model": ErrorResponse, "description": "No heat product is published yet"}},
)
def get_tile(
    request: Request,
    layer: TileLayer,
    z: int = Path(..., ge=0, le=22),
    x: int = Path(..., ge=0),
    y: int = Path(..., ge=0),
) -> FileResponse:
    """
    HTTP GET endpoint serving a pre-rendered tile.

    Args:
        request (Request): Incoming request.
        layer (TileLayer): Whitelisted layer id (blocks any path trickery).
        z (int): Zoom.
        x (int): Tile column.
        y (int): Tile row.

    Returns:
        FileResponse: PNG with a one-day cache header.

    Raises:
        HTTPException: 404 when the tile does not exist; 503 when no product is loaded; 500 for unexpected errors.
    """
    try:
        path = ProductController.tile(request.app.state.store, layer.value, z, x, y)
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
    except HTTPException as httperror:
        raise httperror
    except Exception as error:
        logging.error(f"Error in GET /v1/tiles endpoint: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error"
        ) from error


@router.get(
    "/hotspots",
    response_model=GeoJSONFeatureCollection,
    summary="Hot and cold clusters",
    description="Getis-Ord Gi* clusters of the seasonal mean surface temperature (FDR-controlled). They show "
                "relatively hot or cool areas within the city, not anomalies.",
    responses={404: {"model": ErrorResponse, "description": "No hotspot layer for that season"},
               503: {"model": ErrorResponse, "description": "No heat product is published yet"}},
)
def get_hotspots(request: Request, response: Response, season: Season = Season.SUMMER) -> dict:
    """
    HTTP GET endpoint returning hotspot polygons.

    Args:
        request (Request): Incoming request.
        response (Response): Response used to set cache headers.
        season (Season): Season to report.

    Returns:
        dict: GeoJSON FeatureCollection.

    Raises:
        HTTPException: 404 when the season has no layer; 503 when no product is loaded; 500 for unexpected errors.
    """
    logging.info("Calling GET /v1/hotspots endpoint")
    try:
        response.headers["Cache-Control"] = "public, max-age=3600"
        return ProductController.hotspots(request.app.state.store, season.value)
    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/hotspots endpoint: {httperror}")
        raise httperror
    except Exception as error:
        logging.error(f"Error in GET /v1/hotspots endpoint: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error"
        ) from error
