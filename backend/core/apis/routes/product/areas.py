from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from backend.core import logger
from backend.core.apis.schemas.requests.product.product_request import (
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MIN_LATITUDE,
    MIN_LONGITUDE,
    AssetCategory,
    MetricLayer,
    Season,
)
from backend.core.apis.schemas.responses.error_response import ErrorResponse
from backend.core.apis.schemas.responses.product.catalog_response import (
    CoolingSpotsResponse,
    LocalitySummary,
    ZoneDetail,
    ZoneSummary,
)
from backend.core.apis.schemas.responses.product.heat_response import GeoJSONFeatureCollection
from backend.core.controllers.product_controller import ProductController

logging = logger(__name__)

router = APIRouter(prefix="/v1", tags=["areas"])

ERRORS = {503: {"model": ErrorResponse, "description": "No heat product is published yet"}}
CACHE = "public, max-age=300"


def _internal_error(error: Exception, path: str) -> HTTPException:
    """
    Log an unexpected failure and build the generic 500.

    Args:
        error (Exception): The failure.
        path (str): Endpoint label for the log line.

    Returns:
        HTTPException: Generic 500 (no internals exposed).
    """
    logging.error(f"Error in GET {path} endpoint: {error}")
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")


@router.get("/zones", response_model=list[ZoneSummary], summary="Zone ranking", responses=ERRORS,
            description="The 10 NMC zones for one season, ranked by risk (1 = highest) with 95% rank intervals. "
                        "Zone polygons are approximate.")
def list_zones(request: Request, response: Response, season: Season = Season.SUMMER) -> list[ZoneSummary]:
    """
    HTTP GET endpoint listing zones for a season.

    Args:
        request (Request): Incoming request.
        response (Response): Response used to set cache headers.
        season (Season): Season to report.

    Returns:
        list[ZoneSummary]: Zones sorted by risk rank.

    Raises:
        HTTPException: 503 when no product is loaded; 500 for unexpected errors.
    """
    logging.info("Calling GET /v1/zones endpoint")
    try:
        response.headers["Cache-Control"] = CACHE
        return ProductController.list_zones(request.app.state.store, season.value)
    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/zones endpoint: {httperror}")
        raise httperror
    except Exception as error:
        raise _internal_error(error, "/v1/zones") from error


@router.get("/zones/geojson", response_model=GeoJSONFeatureCollection, summary="Zone polygons with figures",
            responses=ERRORS, description="Zone polygons (WGS84) with the season's figures as properties.")
def zones_geojson(request: Request, response: Response, season: Season = Season.SUMMER) -> dict:
    """
    HTTP GET endpoint returning zone polygons for a choropleth.

    Args:
        request (Request): Incoming request.
        response (Response): Response used to set cache headers.
        season (Season): Season to report.

    Returns:
        dict: GeoJSON FeatureCollection.

    Raises:
        HTTPException: 503 when no product is loaded; 500 for unexpected errors.
    """
    logging.info("Calling GET /v1/zones/geojson endpoint")
    try:
        response.headers["Cache-Control"] = CACHE
        return ProductController.zones_geojson(request.app.state.store, season.value)
    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/zones/geojson endpoint: {httperror}")
        raise httperror
    except Exception as error:
        raise _internal_error(error, "/v1/zones/geojson") from error


@router.get("/zones/{zone_id}", response_model=ZoneDetail, summary="One zone, all seasons",
            responses={**ERRORS, 404: {"model": ErrorResponse, "description": "Unknown zone"}})
def get_zone(request: Request, response: Response, zone_id: int) -> ZoneDetail:
    """
    HTTP GET endpoint returning one zone across all seasons.

    Args:
        request (Request): Incoming request.
        response (Response): Response used to set cache headers.
        zone_id (int): Zone id (1-10).

    Returns:
        ZoneDetail: Zone with per-season figures.

    Raises:
        HTTPException: 404 for an unknown zone; 503 when no product is loaded; 500 for unexpected errors.
    """
    logging.info(f"Calling GET /v1/zones/{zone_id} endpoint")
    try:
        response.headers["Cache-Control"] = CACHE
        return ProductController.get_zone(request.app.state.store, zone_id)
    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/zones/{zone_id} endpoint: {httperror}")
        raise httperror
    except Exception as error:
        raise _internal_error(error, "/v1/zones/{zone_id}") from error


@router.get("/localities", response_model=list[LocalitySummary], summary="Named localities", responses=ERRORS,
            description="55 named localities (revenue villages) traced from the NMC intention map (~100 m), "
                        "with mean surface temperature and exposure for the chosen layer.")
def list_localities(request: Request, response: Response,
                    layer: MetricLayer = MetricLayer.LATEST_SCENE) -> list[LocalitySummary]:
    """
    HTTP GET endpoint listing localities.

    Args:
        request (Request): Incoming request.
        response (Response): Response used to set cache headers.
        layer (MetricLayer): "latest_scene" or a season.

    Returns:
        list[LocalitySummary]: Localities sorted by name.

    Raises:
        HTTPException: 503 when no product is loaded; 500 for unexpected errors.
    """
    logging.info("Calling GET /v1/localities endpoint")
    try:
        response.headers["Cache-Control"] = CACHE
        return ProductController.list_localities(request.app.state.store, layer.value)
    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/localities endpoint: {httperror}")
        raise httperror
    except Exception as error:
        raise _internal_error(error, "/v1/localities") from error


@router.get("/localities/geojson", response_model=GeoJSONFeatureCollection, summary="Locality polygons with figures",
            responses=ERRORS)
def localities_geojson(request: Request, response: Response, layer: MetricLayer = MetricLayer.LATEST_SCENE) -> dict:
    """
    HTTP GET endpoint returning locality polygons with figures.

    Args:
        request (Request): Incoming request.
        response (Response): Response used to set cache headers.
        layer (MetricLayer): "latest_scene" or a season.

    Returns:
        dict: GeoJSON FeatureCollection.

    Raises:
        HTTPException: 503 when no product is loaded; 500 for unexpected errors.
    """
    logging.info("Calling GET /v1/localities/geojson endpoint")
    try:
        response.headers["Cache-Control"] = CACHE
        return ProductController.localities_geojson(request.app.state.store, layer.value)
    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/localities/geojson endpoint: {httperror}")
        raise httperror
    except Exception as error:
        raise _internal_error(error, "/v1/localities/geojson") from error


@router.get("/cooling-spots", response_model=CoolingSpotsResponse, summary="Nearest cooling places",
            responses={**ERRORS, 422: {"model": ErrorResponse, "description": "Invalid or out-of-area coordinates"}},
            description="Parks, water bodies, health facilities, shelters and drinking water near a point, "
                        "nearest first (OpenStreetMap; completeness varies).")
def cooling_spots(
    request: Request,
    response: Response,
    lat: float = Query(..., ge=MIN_LATITUDE, le=MAX_LATITUDE, examples=[21.1458]),
    lon: float = Query(..., ge=MIN_LONGITUDE, le=MAX_LONGITUDE, examples=[79.0882]),
    category: AssetCategory | None = None,
    limit: int = Query(10, ge=1, le=50),
    radius_km: float = Query(5.0, gt=0, le=20),
) -> CoolingSpotsResponse:
    """
    HTTP GET endpoint finding cooling places near a point.

    Args:
        request (Request): Incoming request.
        response (Response): Response used to set cache headers.
        lat (float): Latitude.
        lon (float): Longitude.
        category (AssetCategory | None): Restrict to one category.
        limit (int): Maximum results (1-50).
        radius_km (float): Search radius in km (up to 20).

    Returns:
        CoolingSpotsResponse: Places nearest first.

    Raises:
        HTTPException: 422 outside the study area; 503 when no product is loaded; 500 for unexpected errors.
    """
    logging.info("Calling GET /v1/cooling-spots endpoint")
    try:
        response.headers["Cache-Control"] = "public, max-age=3600"
        return ProductController.cooling_spots(request.app.state.store, lat, lon,
                                               category.value if category else None, limit, radius_km)
    except HTTPException as httperror:
        logging.error(f"Error in GET /v1/cooling-spots endpoint: {httperror}")
        raise httperror
    except Exception as error:
        raise _internal_error(error, "/v1/cooling-spots") from error
