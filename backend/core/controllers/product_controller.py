from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import HTTPException, status

from backend.core import logger
from backend.core.apis.schemas.requests.product.product_request import (
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MAX_ZOOM,
    MIN_LATITUDE,
    MIN_LONGITUDE,
    MIN_ZOOM,
)
from backend.core.apis.schemas.responses.product.catalog_response import (
    CoolingSpot,
    CoolingSpotsResponse,
    LocalitySummary,
    ZoneDetail,
    ZoneSummary,
)
from backend.core.apis.schemas.responses.product.heat_response import (
    HeatResponse,
    LayerInfo,
    Locator,
    MetadataResponse,
    ProductInfo,
    SeasonExposure,
)
from backend.core.config.settings import get_settings
from backend.core.services.product.lookup import (
    EXPOSURE_CODES,
    SEASONS,
    exposure_level,
    finite_or_none,
    haversine_km,
    pixel_for,
    scene_age_days,
)
from backend.core.services.product.store import ProductStore

logging = logger(__name__)

RESOLUTION_NOTE = (
    "30 m analytical grid. Landsat thermal is natively ~100 m resampled to 30 m, so values are per-cell "
    "estimates, not street-level measurements."
)
DISCLAIMERS = [
    "Research tool, not an official warning system. Follow IMD and NMC advisories.",
    "Values are land surface temperature at about 10:00 local solar time, not air temperature or heat index.",
    "Estimates need a recent satellite scene; cloudy cells are filled by a model and marked as not observed.",
]
HEAT_NOTE = "Surface temperature estimate with a 90% range; it is not the air temperature people feel."


def _unavailable() -> HTTPException:
    """
    Build the documented 503 returned when no product bundle is loaded.

    Returns:
        HTTPException: 503 with a stable error code.
    """
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "no_product_available", "message": "No heat product is published yet. Try again later."},
    )


def _outside_area() -> HTTPException:
    """
    Build the documented 422 for coordinates outside the study area.

    Returns:
        HTTPException: 422 with code `outside_study_area`.
    """
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"code": "outside_study_area",
                "message": "That location is outside the HeatSafe study area (Nagpur)."},
    )


def _not_found(what: str) -> HTTPException:
    """
    Build a 404 with a readable message.

    Args:
        what (str): Short description of the missing resource.

    Returns:
        HTTPException: 404.
    """
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} was not found.")


def _require(store: ProductStore | None) -> ProductStore:
    """
    Return the store or raise the documented 503.

    Args:
        store (ProductStore | None): Loaded store, if any.

    Returns:
        ProductStore: The store.

    Raises:
        HTTPException 503: If no product is loaded.
    """
    if store is None:
        logging.warning("Request rejected: no product loaded")
        raise _unavailable()
    return store


class ProductController:
    """
    Builds API answers from the in-memory product (business rules and response assembly).
    """

    @staticmethod
    def product_info(store: ProductStore) -> ProductInfo:
        """
        Describe the loaded product with its age computed now (Decision D2).

        Args:
            store (ProductStore): Loaded product.

        Returns:
            ProductInfo: Version, scene, age, stale flag, and model.
        """
        age = scene_age_days(str(store.pointer["scene_date"]), datetime.now(UTC).date())
        return ProductInfo(
            version=store.version, scene_id=str(store.pointer["scene_id"]), scene_date=str(store.pointer["scene_date"]),
            scene_age_days=age, stale=age > get_settings().max_scene_age_days,
            model_version=str(store.pointer["model_version"]), published_utc=store.pointer.get("published_utc"),
            observed_fraction=store.manifest.get("observed_fraction"),
        )

    @staticmethod
    def get_metadata(store: ProductStore | None) -> MetadataResponse:
        """
        Product description for the frontend.

        Args:
            store (ProductStore | None): Loaded product.

        Returns:
            MetadataResponse: Freshness, extent, layers, and disclaimers.

        Raises:
            HTTPException 503: If no product is loaded.
        """
        logging.info("Executing ProductController.get_metadata")
        loaded = _require(store)
        west, south, east, north = loaded.bounds
        cfg = loaded.manifest["layers"]
        layers = [LayerInfo(id="latest_lst", kind="lst", season=None,
                            tile_url="/api/v1/tiles/latest_lst/{z}/{x}/{y}.png",
                            vmin=cfg["lst"]["vmin"], vmax=cfg["lst"]["vmax"], unit="deg C")]
        for season in SEASONS:
            layers.append(LayerInfo(id=f"lst_{season}", kind="lst", season=season,
                                    tile_url=f"/api/v1/tiles/lst_{season}/{{z}}/{{x}}/{{y}}.png",
                                    vmin=cfg["lst"]["vmin"], vmax=cfg["lst"]["vmax"], unit="deg C"))
        for season in SEASONS:
            layers.append(LayerInfo(id=f"exposure_{season}", kind="exposure", season=season,
                                    tile_url=f"/api/v1/tiles/exposure_{season}/{{z}}/{{x}}/{{y}}.png",
                                    vmin=cfg["exposure"]["vmin"], vmax=cfg["exposure"]["vmax"], unit="index 0-100"))
        return MetadataResponse(
            product=ProductController.product_info(loaded),
            bounds=[round(west, 5), round(south, 5), round(east, 5), round(north, 5)],
            center=[round((west + east) / 2, 5), round((south + north) / 2, 5)],
            zoom_min=MIN_ZOOM, zoom_max=MAX_ZOOM, layers=layers, seasons=list(SEASONS),
            exposure_levels=list(EXPOSURE_CODES), resolution_note=RESOLUTION_NOTE, disclaimers=DISCLAIMERS,
        )

    @staticmethod
    def get_heat(store: ProductStore | None, lat: float, lon: float) -> HeatResponse:
        """
        Heat estimate, 90% range, areas, and seasonal exposure for a point.

        Args:
            store (ProductStore | None): Loaded product.
            lat (float): Latitude (WGS84).
            lon (float): Longitude (WGS84).

        Returns:
            HeatResponse: Answer with freshness and honest caveats.

        Raises:
            HTTPException 503: If no product is loaded.
            HTTPException 422: If the point is outside the study area.
        """
        logging.info("Executing ProductController.get_heat")
        loaded = _require(store)
        cell = ProductController._cell(loaded, lat, lon)
        row, col = cell
        lst = float(loaded.rasters["latest_lst"][row, col])
        covered = bool(np.isfinite(lst))
        locality_id = int(loaded.locality_grid[row, col])
        zone_id = int(loaded.zone_grid[row, col])
        seasons: dict[str, SeasonExposure] = {}
        for season in SEASONS:
            index = finite_or_none(float(loaded.rasters[f"exposure_{season}"][row, col]))
            seasons[season] = SeasonExposure(
                mean_lst_celsius=finite_or_none(float(loaded.rasters[f"lst_{season}"][row, col])),
                exposure_index=index, exposure_level=exposure_level(index),
            )
        return HeatResponse(
            latitude=lat, longitude=lon, covered=covered,
            lst_celsius=finite_or_none(lst),
            lst_p05=finite_or_none(float(loaded.rasters["latest_lst_p05"][row, col])),
            lst_p95=finite_or_none(float(loaded.rasters["latest_lst_p95"][row, col])),
            observed=bool(loaded.rasters["latest_observed_mask"][row, col] > 0.5),
            locality=Locator(id=locality_id, name=str(loaded.localities[locality_id]["locality_name"]))
            if locality_id in loaded.localities else None,
            zone=Locator(id=zone_id, name=str(loaded.zones[zone_id]["zone_name"])) if zone_id in loaded.zones else None,
            seasons=seasons, product=ProductController.product_info(loaded), note=HEAT_NOTE,
        )

    @staticmethod
    def _cell(store: ProductStore, lat: float, lon: float) -> tuple[int, int]:
        """
        Grid cell for a point, enforcing the study-area limits.

        Args:
            store (ProductStore): Loaded product.
            lat (float): Latitude.
            lon (float): Longitude.

        Returns:
            tuple[int, int]: (row, col).

        Raises:
            HTTPException 422: If the point is outside the study area or the product grid.
        """
        if not (MIN_LATITUDE <= lat <= MAX_LATITUDE and MIN_LONGITUDE <= lon <= MAX_LONGITUDE):
            raise _outside_area()
        cell = pixel_for(lat, lon, store.transform, store.crs, store.shape)
        if cell is None:
            raise _outside_area()
        return cell

    @staticmethod
    def _zone_summary(record: dict[str, Any]) -> ZoneSummary:
        """
        Convert a zone metrics record into the response model.

        Args:
            record (dict[str, Any]): Row from `zone_metrics.json`.

        Returns:
            ZoneSummary: Response model with cooling-asset counts.
        """
        fields = set(ZoneSummary.model_fields) - {"assets"}
        data = {k: v for k, v in record.items() if k in fields}
        data["assets"] = {k.removeprefix("assets_"): int(v) for k, v in record.items() if k.startswith("assets_")}
        return ZoneSummary(**data)

    @staticmethod
    def list_zones(store: ProductStore | None, season: str) -> list[ZoneSummary]:
        """
        All zones for one season, ranked by risk (1 = highest).

        Args:
            store (ProductStore | None): Loaded product.
            season (str): Season name.

        Returns:
            list[ZoneSummary]: Zones sorted by risk rank.

        Raises:
            HTTPException 503: If no product is loaded.
        """
        logging.info("Executing ProductController.list_zones")
        loaded = _require(store)
        rows = [ProductController._zone_summary(r) for r in loaded.zone_metrics if r["season"] == season]
        return sorted(rows, key=lambda z: (z.risk_rank is None, z.risk_rank))

    @staticmethod
    def get_zone(store: ProductStore | None, zone_id: int) -> ZoneDetail:
        """
        One zone with its figures for every season.

        Args:
            store (ProductStore | None): Loaded product.
            zone_id (int): Zone id.

        Returns:
            ZoneDetail: Zone with per-season figures.

        Raises:
            HTTPException 503: If no product is loaded.
            HTTPException 404: If the zone does not exist.
        """
        logging.info("Executing ProductController.get_zone")
        loaded = _require(store)
        rows = [r for r in loaded.zone_metrics if int(r["zone_id"]) == zone_id]
        if not rows:
            logging.warning(f"Zone {zone_id} not found")
            raise _not_found(f"Zone {zone_id}")
        return ZoneDetail(zone_id=zone_id, zone_name=str(rows[0]["zone_name"]), area_km2=float(rows[0]["area_km2"]),
                          seasons={str(r["season"]): ProductController._zone_summary(r) for r in rows})

    @staticmethod
    def zones_geojson(store: ProductStore | None, season: str) -> dict[str, Any]:
        """
        Zone polygons with the season's figures as properties (ready for a choropleth).

        Args:
            store (ProductStore | None): Loaded product.
            season (str): Season name.

        Returns:
            dict[str, Any]: FeatureCollection.

        Raises:
            HTTPException 503: If no product is loaded.
        """
        logging.info("Executing ProductController.zones_geojson")
        loaded = _require(store)
        by_id = {z.zone_id: z for z in ProductController.list_zones(loaded, season)}
        features = []
        for feature in loaded.zone_features:
            zone = by_id.get(int(feature["properties"]["zone_id"]))
            properties = zone.model_dump() if zone else dict(feature["properties"])
            features.append({"type": "Feature", "geometry": feature["geometry"], "properties": properties})
        return {"type": "FeatureCollection", "features": features,
                "properties": {"season": season, "boundary_quality": "approximate; not an official zone map"}}

    @staticmethod
    def list_localities(store: ProductStore | None, layer: str) -> list[LocalitySummary]:
        """
        Named localities with mean LST and exposure for a layer.

        Args:
            store (ProductStore | None): Loaded product.
            layer (str): "latest_scene" or a season.

        Returns:
            list[LocalitySummary]: Localities sorted by name.

        Raises:
            HTTPException 503: If no product is loaded.
        """
        logging.info("Executing ProductController.list_localities")
        loaded = _require(store)
        rows = []
        for record in loaded.locality_metrics:
            if record["layer"] != layer:
                continue
            props = loaded.localities[int(record["locality_id"])]
            rows.append(LocalitySummary(
                locality_id=int(record["locality_id"]), locality_name=str(props["locality_name"]),
                area_km2=float(props["area_km2"]), in_extended_limit=bool(props["in_extended_limit"]), layer=layer,
                mean_lst_celsius=record.get("mean_lst_celsius"), exposure_index=record.get("exposure_index"),
                exposure_level=record.get("exposure_level"),
            ))
        return sorted(rows, key=lambda r: r.locality_name)

    @staticmethod
    def localities_geojson(store: ProductStore | None, layer: str) -> dict[str, Any]:
        """
        Locality polygons with the layer's figures as properties.

        Args:
            store (ProductStore | None): Loaded product.
            layer (str): "latest_scene" or a season.

        Returns:
            dict[str, Any]: FeatureCollection.

        Raises:
            HTTPException 503: If no product is loaded.
        """
        logging.info("Executing ProductController.localities_geojson")
        loaded = _require(store)
        by_id = {r.locality_id: r for r in ProductController.list_localities(loaded, layer)}
        features = []
        for feature in loaded.locality_features:
            row = by_id.get(int(feature["properties"]["locality_id"]))
            properties = row.model_dump() if row else dict(feature["properties"])
            features.append({"type": "Feature", "geometry": feature["geometry"], "properties": properties})
        return {"type": "FeatureCollection", "features": features,
                "properties": {"layer": layer, "boundary_quality": "traced from the NMC intention map, ~100 m"}}

    @staticmethod
    def cooling_spots(store: ProductStore | None, lat: float, lon: float, category: str | None, limit: int,
                      radius_km: float) -> CoolingSpotsResponse:
        """
        Nearest cooling-related places to a point.

        Args:
            store (ProductStore | None): Loaded product.
            lat (float): Latitude.
            lon (float): Longitude.
            category (str | None): Restrict to one category, or None for all.
            limit (int): Maximum results.
            radius_km (float): Search radius.

        Returns:
            CoolingSpotsResponse: Spots nearest first.

        Raises:
            HTTPException 503: If no product is loaded.
            HTTPException 422: If the point is outside the study area.
        """
        logging.info("Executing ProductController.cooling_spots")
        loaded = _require(store)
        ProductController._cell(loaded, lat, lon)
        distance = haversine_km(lat, lon, loaded.asset_lats, loaded.asset_lons)
        keep = distance <= radius_km
        if category is not None:
            keep &= loaded.asset_categories == category
        order = np.flatnonzero(keep)[np.argsort(distance[keep])][:limit]
        spots = [CoolingSpot(asset_id=loaded.asset_ids[i], category=str(loaded.asset_categories[i]),
                             name=loaded.asset_names[i], latitude=float(loaded.asset_lats[i]),
                             longitude=float(loaded.asset_lons[i]), distance_km=round(float(distance[i]), 3))
                 for i in order]
        return CoolingSpotsResponse(latitude=lat, longitude=lon, radius_km=radius_km, count=len(spots), spots=spots)

    @staticmethod
    def hotspots(store: ProductStore | None, season: str) -> dict[str, Any]:
        """
        Gi* hot and cold cluster polygons for a season.

        Args:
            store (ProductStore | None): Loaded product.
            season (str): Season name.

        Returns:
            dict[str, Any]: FeatureCollection.

        Raises:
            HTTPException 503: If no product is loaded.
            HTTPException 404: If the season has no hotspot layer.
        """
        logging.info("Executing ProductController.hotspots")
        loaded = _require(store)
        if season not in loaded.hotspots:
            raise _not_found(f"Hotspot layer for {season}")
        return dict(loaded.hotspots[season])

    @staticmethod
    def tile(store: ProductStore | None, layer: str, z: int, x: int, y: int) -> Path:
        """
        Locate a pre-rendered tile.

        Args:
            store (ProductStore | None): Loaded product.
            layer (str): Whitelisted layer id.
            z (int): Zoom.
            x (int): Tile column.
            y (int): Tile row.

        Returns:
            Path: PNG path.

        Raises:
            HTTPException 503: If no product is loaded.
            HTTPException 404: If the tile does not exist (outside the study area or no data).
        """
        loaded = _require(store)
        if not MIN_ZOOM <= z <= MAX_ZOOM:
            raise _not_found("Tile")
        path = loaded.tile_path(layer, z, x, y)
        if path is None:
            raise _not_found("Tile")
        return path
