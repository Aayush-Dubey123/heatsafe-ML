import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

CRS = "EPSG:32644"
ORIGIN_EASTING, ORIGIN_NORTHING, CELL, SIZE = 299000.0, 2341000.0, 30.0, 60
SEASONS = ("summer", "monsoon", "post-monsoon", "winter")
WATER_CELL = (5, 5)  # row, col left empty in the latest-scene rasters
LEVEL_BREAKS = [25.0, 50.0, 75.0, 90.0]


def grid_bounds_wgs84() -> tuple[float, float, float, float]:
    """
    WGS84 bounds of the small synthetic grid.

    Returns:
        tuple[float, float, float, float]: (west, south, east, north).
    """
    return transform_bounds(CRS, "EPSG:4326", ORIGIN_EASTING, ORIGIN_NORTHING - SIZE * CELL,
                            ORIGIN_EASTING + SIZE * CELL, ORIGIN_NORTHING)


def write_raster(path: Path, array: np.ndarray) -> None:
    """
    Write a float32 GeoTIFF on the synthetic grid.

    Args:
        path (Path): Output file.
        array (np.ndarray): 2D array.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=SIZE, width=SIZE, count=1, dtype="float32", crs=CRS,
                       transform=from_origin(ORIGIN_EASTING, ORIGIN_NORTHING, CELL, CELL), nodata=np.nan) as dst:
        dst.write(array.astype(np.float32), 1)


def polygon(west: float, south: float, east: float, north: float) -> dict:
    """
    Rectangle polygon geometry.

    Args:
        west (float): West longitude.
        south (float): South latitude.
        east (float): East longitude.
        north (float): North latitude.

    Returns:
        dict: GeoJSON Polygon.
    """
    return {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north],
                                                [west, south]]]}


def build_bundle(root: Path, scene_age_days: int = 3, version: str = "test-bundle") -> dict:
    """
    Build a small but complete product bundle and its latest.json pointer.

    Args:
        root (Path): Published folder.
        scene_age_days (int): Age of the scene relative to now.
        version (str): Bundle version.

    Returns:
        dict: Facts the tests assert on (center point, area names, tile path).
    """
    bundle = root / version
    west, south, east, north = grid_bounds_wgs84()
    mid = (west + east) / 2
    rows, cols = np.indices((SIZE, SIZE))
    lst = 30.0 + cols * 0.1
    lst[WATER_CELL] = np.nan
    observed = ((rows + cols) % 2 == 0).astype(np.float32)
    write_raster(bundle / "cogs" / "latest_lst.tif", lst)
    write_raster(bundle / "cogs" / "latest_lst_p05.tif", lst - 1.5)
    write_raster(bundle / "cogs" / "latest_lst_p95.tif", lst + 1.5)
    write_raster(bundle / "cogs" / "latest_observed_mask.tif", observed)
    for number, season in enumerate(SEASONS):
        write_raster(bundle / "cogs" / f"lst_{season}.tif", 40.0 + number + cols * 0.05)
        write_raster(bundle / "cogs" / f"exposure_{season}.tif", np.clip(cols * 1.6 + number, 0, 100))

    zones = [("Zone West", 1, (west, south, mid, north)), ("Zone East", 2, (mid, south, east, north))]
    localities = [("Locality North", 1, (west, (south + north) / 2, east, north)),
                  ("Locality South", 2, (west, south, east, (south + north) / 2))]
    vectors = bundle / "vectors"
    vectors.mkdir(parents=True)
    (vectors / "zones.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"zone_id": zid, "zone_name": name}, "geometry": polygon(*box)}
        for name, zid, box in zones]}))
    (vectors / "localities.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"locality_id": lid, "locality_name": name, "area_km2": 1.5,
                                           "in_extended_limit": lid == 2}, "geometry": polygon(*box)}
        for name, lid, box in localities]}))
    center_lon, center_lat = (west + east) / 2 + 0.0005, (south + north) / 2
    assets = [("osm-node-1", "green_space", "Near Park", 0.0005, 0.0), ("osm-node-2", "water_body", "Lake", 0.002, 0.0),
              ("osm-node-3", "health_facility", None, 0.001, 0.001),
              ("osm-node-4", "green_space", "Far Park", 0.05, 0.0)]
    (vectors / "cooling_assets.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"asset_id": aid, "category": cat, "name": name},
         "geometry": {"type": "Point", "coordinates": [center_lon + dlon, center_lat + dlat]}}
        for aid, cat, name, dlon, dlat in assets]}))
    (vectors / "hotspots_summer.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"cluster": "hot"}, "geometry": polygon(west, south, mid, north)}]}))

    tables = bundle / "tables"
    tables.mkdir()
    zone_rows = []
    for name, zid, _ in zones:
        for number, season in enumerate(SEASONS):
            zone_rows.append({
                "zone_id": zid, "zone_name": name, "area_km2": 2.0, "season": season, "mean_lst_celsius": 40.0 + number,
                "exposure_index": 30.0 + zid * 10, "exposure_index_ci_low": 25.0, "exposure_index_ci_high": 45.0,
                "exposure_level": "moderate", "exposure_rank": zid, "vulnerability_score": 50.0,
                "risk_score": 40.0 + zid,
                "risk_rank": 3 - zid, "risk_rank_low": 1, "risk_rank_high": 2, "population": 1000 * zid,
                "population_density_per_km2": 500.0, "share_age_60_plus": 0.1096, "green_deficit": 0.5,
                "assets_green_space": zid + 1, "assets_water_body": 0, "scene_count": 40, "mean_ndvi": 0.3,
            })
    (tables / "zone_metrics.json").write_text(json.dumps(zone_rows))
    locality_rows = [{"locality_id": lid, "layer": layer, "mean_lst_celsius": 41.0 + lid, "exposure_index": 55.0,
                      "exposure_level": "high"}
                     for _, lid, _ in localities for layer in ("latest_scene", *SEASONS)]
    (tables / "locality_metrics.json").write_text(json.dumps(locality_rows))

    tile = bundle / "tiles" / "latest_lst" / "12" / "100" / "200.png"
    tile.parent.mkdir(parents=True)
    tile.write_bytes(b"\x89PNG\r\n\x1a\n-test-tile")
    manifest = {"version": version, "observed_fraction": 0.5, "file_count": 0, "files": [],
                "layers": {"lst": {"vmin": 20.0, "vmax": 60.0}, "exposure": {"vmin": 0.0, "vmax": 100.0}}}
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    scene_date = (datetime.now(UTC) - timedelta(days=scene_age_days)).date().isoformat()
    (root / "latest.json").write_text(json.dumps({
        "version": version, "scene_id": "LC09_TEST", "scene_date": scene_date, "model_version": "m1-test",
        "published_utc": "2026-11-11T05:00:00+00:00"}))
    return {"lat": center_lat, "lon": center_lon, "scene_date": scene_date, "west_lon": west + 0.001,
            "east_lon": east - 0.001, "water_lat_lon": water_point()}


def water_point() -> tuple[float, float]:
    """
    Latitude and longitude of the centre of the empty (water) cell.

    Returns:
        tuple[float, float]: (lat, lon).
    """
    from rasterio.warp import transform

    easting = ORIGIN_EASTING + (WATER_CELL[1] + 0.5) * CELL
    northing = ORIGIN_NORTHING - (WATER_CELL[0] + 0.5) * CELL
    lons, lats = transform(CRS, "EPSG:4326", [easting], [northing])
    return lats[0], lons[0]
