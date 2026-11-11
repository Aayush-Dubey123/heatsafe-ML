"""
HeatSafe-ML versioned data products (Phase 9).

A product bundle is everything the API serves for one satellite scene:

  ml/data/published/<version>/
    cogs/        latest-scene LST + 5th/95th percentile bounds, seasonal mean LST, exposure index
    tiles/       pre-rendered PNG XYZ tiles per layer
    vectors/     zones, localities, cooling assets, hotspots (GeoJSON, EPSG:4326)
    tables/      zone and locality metrics (JSON)
    manifest.json  every file with size and SHA-256

`latest.json` next to the bundles is switched atomically, so readers never see a
half-written bundle. The model is applied here, in batch; the API never runs it.

Usage:
    python -m ml.src.publish.products            # build + publish the newest usable scene
    python -m ml.src.publish.products --load-db  # also load tables into the database
"""

import argparse
import json
import os
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import rasterio
from rasterio.shutil import copy as rio_copy

from ml.src.commons.logger import get_ml_logger
from ml.src.dataset.build import (
    FOCAL_WINDOWS,
    INTERIM_DIR,
    PROCESSED_DIR,
    SCENE_INDEX,
    SCENES_DIR,
    focal_mean,
    grid_geometry,
    scene_seed,
)
from ml.src.dataset.splits import load_thresholds
from ml.src.eda.maps import write_geotiff
from ml.src.exposure.index import BOUNDARY_DIR, ZONES_PATH, exposure_levels, rasterize_zones, zone_means
from ml.src.models.baseline.baselines import idw
from ml.src.models.core.evaluate import sha256_file
from ml.src.preprocess.align import load_master_grid_spec
from ml.src.publish.tiles import render_layer_tiles
from ml.src.validation.final_test import latest_model_dir

logging = get_ml_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
LOCALITIES_PATH = BOUNDARY_DIR / "nagpur_localities.geojson"
CLIMATOLOGY_PATH = INTERIM_DIR / "index_climatology.npz"
SEASONS = ("summer", "monsoon", "post-monsoon", "winter")
INDEX_NAMES = ("ndvi", "ndbi", "mndwi")


def published_dir() -> Path:
    """
    Root folder holding product bundles and the `latest.json` pointer.

    Returns:
        Path: Absolute path (configured in thresholds.yaml, overridable with HEATSAFE_PUBLISHED_DIR).
    """
    override = os.environ.get("HEATSAFE_PUBLISHED_DIR")
    return Path(override) if override else REPO_ROOT / load_thresholds()["publish"]["published_dir"]


def index_climatology(scene_index: pd.DataFrame, scenes_dir: Path = SCENES_DIR) -> dict[str, np.ndarray]:
    """
    Long-term mean NDVI, NDBI, and MNDWI per pixel from clear training-window observations.

    Used to fill spectral indices where the current scene is cloudy, so the model
    can still estimate LST there. Cached in the interim folder.

    Args:
        scene_index (pd.DataFrame): Scene index from the dataset builder.
        scenes_dir (Path): Folder of scene cubes.

    Returns:
        dict[str, np.ndarray]: Grid-shaped float32 arrays keyed by index name (NaN = never observed).
    """
    if CLIMATOLOGY_PATH.is_file():
        with np.load(CLIMATOLOGY_PATH) as cached:
            return {name: cached[name] for name in INDEX_NAMES}
    shape = tuple(load_master_grid_spec()["shape"])
    totals = {name: np.zeros(shape, dtype=np.float64) for name in INDEX_NAMES}
    count = np.zeros(shape, dtype=np.float64)
    usable = scene_index[scene_index["usable"] & (scene_index["split"] == "train")]
    for scene_id in usable["scene_id"]:
        with np.load(scenes_dir / f"{scene_id}.npz") as cube:
            ok = cube["trainable"]
            for name in INDEX_NAMES:
                totals[name][ok] += cube[name][ok]
            count[ok] += 1
    with np.errstate(invalid="ignore", divide="ignore"):
        result = {name: np.where(count > 0, totals[name] / count, np.nan).astype(np.float32) for name in INDEX_NAMES}
    np.savez_compressed(CLIMATOLOGY_PATH, **result)
    return result


def predict_scene_grid(cube: dict[str, Any], terrain: dict[str, np.ndarray], climatology: dict[str, np.ndarray],
                       model_dir: Path, sample_pixels: int, seed: int) -> dict[str, np.ndarray]:
    """
    Model 1 estimate of LST with a 90% range for every land cell of one scene.

    The scene anchor and the kriged residuals come from the scene's own clear
    pixels. Cloudy cells use long-term mean spectral indices. Open water and
    cells without terrain data are left empty.

    Args:
        cube (dict[str, Any]): Scene arrays (lst, ndvi, ndbi, mndwi, trainable, is_water) and metadata.
        terrain (dict[str, np.ndarray]): elevation, slope, aspect, valid_dem.
        climatology (dict[str, np.ndarray]): Long-term mean indices.
        model_dir (Path): Registered model folder.
        sample_pixels (int): Clear pixels used for residual kriging.
        seed (int): Sampling seed.

    Returns:
        dict[str, np.ndarray]: 'lst', 'lst_p05', 'lst_p95' (float32 grids, NaN = no estimate) and
        'observed' (bool grid: True where the scene had a clear observation).

    Raises:
        ValueError: If the scene has no clear pixels to anchor on.
    """
    spec = load_master_grid_spec()
    shape = tuple(spec["shape"])
    metadata = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
    features = metadata["features"]
    trainable = cube["trainable"].astype(bool)
    if not trainable.any():
        raise ValueError("Scene has no clear land pixels")
    geometry = grid_geometry()
    meta = cube["metadata"]

    indices = {}
    for name in INDEX_NAMES:
        current = cube[name].astype(np.float32)
        indices[name] = np.where(trainable, current, climatology[name])
    frame = pd.DataFrame({
        "elevation": terrain["elevation"].ravel(),
        "slope": terrain["slope"].ravel(),
        "ndvi": indices["ndvi"].ravel(),
        "ndbi": indices["ndbi"].ravel(),
        "mndwi": indices["mndwi"].ravel(),
    })
    aspect = terrain["aspect"].ravel().astype(np.float64)
    flat_aspect = aspect < 0
    frame["aspect_sin"] = np.where(flat_aspect, 0.0, np.sin(np.deg2rad(aspect))).astype(np.float32)
    frame["aspect_cos"] = np.where(flat_aspect, 0.0, np.cos(np.deg2rad(aspect))).astype(np.float32)
    for name in INDEX_NAMES:
        for label, window in FOCAL_WINDOWS.items():
            frame[f"{name}_{label}"] = focal_mean(indices[name], window).ravel()
    frame["sin_doy"] = np.float32(meta["sin_doy"])
    frame["cos_doy"] = np.float32(meta["cos_doy"])
    frame["mean_solar_hour"] = ((float(meta["utc_decimal"]) + geometry["longitude"] / 15.0) % 24.0).astype(np.float32)
    observed_lst = cube["lst"].ravel().astype(np.float64)
    clear = trainable.ravel() & np.isfinite(observed_lst)
    anchor = float(observed_lst[clear].mean())
    frame["scene_anchor_lst"] = anchor

    boosters = {name: lgb.Booster(model_file=str(model_dir / f"{name}.txt")) for name in ("point", "lower", "upper")}
    x = frame[features]
    point = anchor + boosters["point"].predict(x)
    lower = anchor + boosters["lower"].predict(x)
    upper = anchor + boosters["upper"].predict(x)

    if metadata.get("residual_kriging"):
        candidates = np.flatnonzero(clear)
        rng = np.random.default_rng(seed)
        chosen = np.sort(rng.choice(candidates, size=min(sample_pixels, candidates.size), replace=False))
        xy = np.column_stack([geometry["easting"], geometry["northing"]])
        correction = idw(xy[chosen], observed_lst[chosen] - point[chosen], xy, 12, 2.0)
        point, lower, upper = point + correction, lower + correction, upper + correction

    valid = terrain["valid_dem"].ravel().astype(bool) & ~cube["is_water"].ravel().astype(bool)
    valid &= np.isfinite(frame["ndvi"].to_numpy()) & np.isfinite(point)
    low, high = np.minimum(lower, upper), np.maximum(lower, upper)
    return {
        "lst": np.where(valid, point, np.nan).astype(np.float32).reshape(shape),
        "lst_p05": np.where(valid, low, np.nan).astype(np.float32).reshape(shape),
        "lst_p95": np.where(valid, high, np.nan).astype(np.float32).reshape(shape),
        "observed": (clear & valid).reshape(shape),
    }


def load_cube(scene_id: str, scenes_dir: Path = SCENES_DIR) -> dict[str, Any]:
    """
    Read one scene cube into memory.

    Args:
        scene_id (str): Landsat scene id.
        scenes_dir (Path): Folder of scene cubes.

    Returns:
        dict[str, Any]: Arrays plus parsed 'metadata'.
    """
    with np.load(scenes_dir / f"{scene_id}.npz") as data:
        cube: dict[str, Any] = {key: data[key] for key in ("lst", "ndvi", "ndbi", "mndwi", "trainable", "is_water")}
        cube["metadata"] = json.loads(str(data["metadata"]))
    return cube


def write_cog(path: Path, array: np.ndarray, tags: dict[str, str]) -> None:
    """
    Write a Cloud-Optimized GeoTIFF on the master grid (EPSG:32644).

    Args:
        path (Path): Destination .tif.
        array (np.ndarray): 2D float raster (NaN = no data).
        tags (dict[str, str]): Metadata tags.
    """
    temporary = path.with_name(path.stem + "_tmp.tif")
    write_geotiff(temporary, array, tags)
    rio_copy(str(temporary), str(path), driver="COG", compress="DEFLATE", overview_resampling="average")
    temporary.unlink()


def area_metrics(raster: np.ndarray, area_ids: list[int], layers: dict[str, np.ndarray],
                 exposure: dict[str, np.ndarray], breaks: list[float], codes: list[str]) -> list[dict[str, Any]]:
    """
    Mean LST and exposure per area for each layer.

    Args:
        raster (np.ndarray): Area id raster on the master grid.
        area_ids (list[int]): Areas to report.
        layers (dict[str, np.ndarray]): Layer name → LST raster.
        exposure (dict[str, np.ndarray]): Layer name → exposure-index raster (may be missing for a layer).
        breaks (list[float]): Exposure level cut-offs.
        codes (list[str]): Exposure level codes.

    Returns:
        list[dict[str, Any]]: One row per (area, layer).
    """
    flat = raster.ravel()
    rows: list[dict[str, Any]] = []
    for layer, lst in layers.items():
        mean_lst = zone_means(lst.ravel().astype(np.float64), flat, area_ids)
        index = zone_means(exposure[layer].ravel().astype(np.float64), flat, area_ids) if layer in exposure else None
        levels = exposure_levels(index, breaks, codes) if index is not None else None
        for position, area_id in enumerate(area_ids):
            value = None if index is None or not np.isfinite(index[position]) else round(float(index[position]), 2)
            rows.append({
                "locality_id": int(area_id), "layer": layer,
                "mean_lst_celsius": (
                    round(float(mean_lst[position]), 2) if np.isfinite(mean_lst[position]) else None
                ),
                "exposure_index": value,
                "exposure_level": None if levels is None or value is None else str(levels[position]),
            })
    return rows


def write_manifest(bundle: Path, header: dict[str, Any]) -> dict[str, Any]:
    """
    Hash every file of a bundle and write `manifest.json`.

    Args:
        bundle (Path): Bundle folder.
        header (dict[str, Any]): Version, scene, and model fields.

    Returns:
        dict[str, Any]: The manifest (also saved to disk).
    """
    files = []
    for path in sorted(p for p in bundle.rglob("*") if p.is_file() and p.name != "manifest.json"):
        files.append({"path": path.relative_to(bundle).as_posix(), "bytes": path.stat().st_size,
                      "sha256": sha256_file(path)})
    manifest = {**header, "file_count": len(files), "files": files}
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def freshness(scene_date: str, today: date, max_age_days: int) -> dict[str, Any]:
    """
    Age of a scene and whether it is stale (Decision D2).

    Args:
        scene_date (str): Acquisition date, YYYY-MM-DD.
        today (date): Reference date.
        max_age_days (int): Staleness limit.

    Returns:
        dict[str, Any]: scene_age_days and stale.
    """
    age = (today - date.fromisoformat(scene_date)).days
    return {"scene_age_days": int(age), "stale": bool(age > max_age_days)}


def set_latest(root: Path, pointer: dict[str, Any]) -> None:
    """
    Atomically replace `latest.json`.

    Args:
        root (Path): Published root folder.
        pointer (dict[str, Any]): New pointer content.
    """
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / "latest.json.tmp"
    temporary.write_text(json.dumps(pointer, indent=1), encoding="utf-8")
    os.replace(temporary, root / "latest.json")


def read_latest(root: Path) -> dict[str, Any] | None:
    """
    Read the current `latest.json` pointer.

    Args:
        root (Path): Published root folder.

    Returns:
        dict[str, Any] | None: Pointer, or None when nothing has been published.
    """
    path = root / "latest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def newest_usable_scene(scene_index: pd.DataFrame) -> dict[str, Any]:
    """
    Pick the most recent usable scene.

    Args:
        scene_index (pd.DataFrame): Scene index from the dataset builder.

    Returns:
        dict[str, Any]: Row with scene_id and date.

    Raises:
        ValueError: If no usable scene exists.
    """
    usable = scene_index[scene_index["usable"]].sort_values("date")
    if usable.empty:
        raise ValueError("No usable scene to publish")
    return usable.iloc[-1].to_dict()


def build_bundle(scene_id: str | None = None, with_tiles: bool = True, today: date | None = None) -> dict[str, Any]:
    """
    Build and publish the product bundle for one scene (default: the newest usable scene).

    Publishing is idempotent: if the bundle for this version already exists with an
    identical manifest, nothing is rewritten and only the pointer is refreshed.

    Args:
        scene_id (str | None): Scene to publish; None picks the newest usable scene.
        with_tiles (bool): Render PNG tiles (slowest step).
        today (date | None): Reference date for freshness (defaults to the current UTC date).

    Returns:
        dict[str, Any]: version, bundle path, changed flag, tile counts, freshness.
    """
    thresholds = load_thresholds()
    cfg = thresholds["publish"]
    exposure_cfg = thresholds["exposure"]
    today = today or datetime.now(UTC).date()
    root = published_dir()
    scene_index = pd.read_parquet(SCENE_INDEX)
    row = (scene_index[scene_index["scene_id"] == scene_id].iloc[0].to_dict() if scene_id
           else newest_usable_scene(scene_index))
    model_dir = latest_model_dir()
    version = f"{row['date']}_{row['scene_id']}_{model_dir.name}"
    bundle = root / version
    fresh = freshness(str(row["date"]), today, int(thresholds["freshness_rules"]["max_scene_age_days"]))

    if (bundle / "manifest.json").is_file():
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        intact = all((bundle / f["path"]).is_file() and sha256_file(bundle / f["path"]) == f["sha256"]
                     for f in manifest["files"])
        if intact:
            set_latest(root, {"version": version, "scene_id": row["scene_id"], "scene_date": str(row["date"]),
                              "model_version": model_dir.name, "published_utc": manifest["created_utc"], **fresh})
            logging.info(f"Bundle {version} already published and intact; nothing rewritten")
            return {"version": version, "bundle": str(bundle), "changed": False, **fresh}

    staging = root / f".staging_{version}"
    shutil.rmtree(staging, ignore_errors=True)
    (staging / "cogs").mkdir(parents=True)
    (staging / "vectors").mkdir()
    (staging / "tables").mkdir()

    with np.load(INTERIM_DIR / "static_terrain.npz") as terrain_file:
        terrain = {key: terrain_file[key] for key in ("elevation", "slope", "aspect", "valid_dem")}
    cube = load_cube(str(row["scene_id"]))
    grids = predict_scene_grid(cube, terrain, index_climatology(scene_index), model_dir,
                               int(cfg["kriging_sample_pixels"]),
                               scene_seed(str(row["scene_id"]), int(cfg["random_seed"])))
    common = {"scene_id": str(row["scene_id"]), "scene_date": str(row["date"]), "model_version": model_dir.name,
              "caveat": "land surface temperature at ~10:00 local solar time; not air temperature; 30 m grid, "
                        "thermal band native ~100 m"}
    for name, label in (("lst", "Model 1 LST estimate (deg C)"), ("lst_p05", "5th percentile bound (deg C)"),
                        ("lst_p95", "95th percentile bound (deg C)")):
        write_cog(staging / "cogs" / f"latest_{name}.tif", grids[name], {"variable": label, **common})
    write_cog(staging / "cogs" / "latest_observed_mask.tif", grids["observed"].astype(np.float32),
              {"variable": "1 where the scene had a clear observation, 0 where the value is model-filled", **common})

    lst_layers: dict[str, np.ndarray] = {"latest_scene": grids["lst"]}
    exposure_layers: dict[str, np.ndarray] = {}
    for season in SEASONS:
        mean_path = PROCESSED_DIR / "maps" / f"lst_{season}_2019_2025.tif"
        index_path = PROCESSED_DIR / "exposure" / f"exposure_index_{season}.tif"
        with rasterio.open(mean_path) as src:
            lst_layers[season] = src.read(1)
            write_cog(staging / "cogs" / f"lst_{season}.tif", lst_layers[season], dict(src.tags()))
        with rasterio.open(index_path) as src:
            exposure_layers[season] = src.read(1)
            write_cog(staging / "cogs" / f"exposure_{season}.tif", exposure_layers[season], dict(src.tags()))
        hotspots = PROCESSED_DIR / "maps" / f"hotspots_{season}.geojson"
        if hotspots.is_file():
            shutil.copyfile(hotspots, staging / "vectors" / f"hotspots_{season}.geojson")

    shutil.copyfile(ZONES_PATH, staging / "vectors" / "zones.geojson")
    shutil.copyfile(LOCALITIES_PATH, staging / "vectors" / "localities.geojson")
    shutil.copyfile(PROCESSED_DIR / "exposure" / "cooling_assets.geojson",
                    staging / "vectors" / "cooling_assets.geojson")

    zone_table = pd.read_parquet(PROCESSED_DIR / "exposure" / "exposure_zone.parquet")
    (staging / "tables" / "zone_metrics.json").write_text(zone_table.to_json(orient="records"), encoding="utf-8")
    locality_raster, locality_table = rasterize_zones(LOCALITIES_PATH, "locality_id", "locality_name")
    locality_rows = area_metrics(locality_raster, [int(v) for v in locality_table["zone_id"]], lst_layers,
                                 exposure_layers, list(exposure_cfg["level_breaks"]), list(exposure_cfg["level_codes"]))
    (staging / "tables" / "locality_metrics.json").write_text(json.dumps(locality_rows), encoding="utf-8")

    tile_summary: dict[str, Any] = {}
    if with_tiles:
        layer_cfg = cfg["layers"]
        jobs = [("latest_lst", grids["lst"], layer_cfg["lst"])]
        jobs += [(f"lst_{season}", lst_layers[season], layer_cfg["lst"]) for season in SEASONS]
        jobs += [(f"exposure_{season}", exposure_layers[season], layer_cfg["exposure"]) for season in SEASONS]
        for name, array, one_cfg in jobs:
            tile_summary[name] = render_layer_tiles(array, staging / "tiles" / name, one_cfg,
                                                    int(cfg["tile_zoom_min"]), int(cfg["tile_zoom_max"]),
                                                    int(cfg["tile_size"]))

    created = datetime.now(UTC).isoformat()
    write_manifest(staging, {
        "version": version, **common, "created_utc": created,
        "observed_fraction": round(float(grids["observed"].mean()), 4),
        "layers": {"lst": cfg["layers"]["lst"], "exposure": cfg["layers"]["exposure"]},
        "tiles": {name: {"tiles": s["tiles"], "per_zoom": s["per_zoom"]} for name, s in tile_summary.items()},
        "crs": {"rasters": "EPSG:32644", "vectors": "EPSG:4326", "tiles": "EPSG:3857 (XYZ)"},
    })
    shutil.rmtree(bundle, ignore_errors=True)
    os.replace(staging, bundle)
    set_latest(root, {"version": version, "scene_id": str(row["scene_id"]), "scene_date": str(row["date"]),
                      "model_version": model_dir.name, "published_utc": created, **fresh})
    logging.info(f"Published bundle {version}")
    return {"version": version, "bundle": str(bundle), "changed": True, "tiles": tile_summary, **fresh}


def load_bundle_to_database(bundle: Path, database_url: str) -> dict[str, int]:
    """
    Load a bundle's tables into the serving database in one transaction.

    Reference tables (zones, localities, cooling assets) are replaced; metric rows
    for this product version are replaced; the product row is upserted and marked latest.

    Args:
        bundle (Path): Published bundle folder.
        database_url (str): SQLAlchemy URL of the serving database (schema created by Alembic).

    Returns:
        dict[str, int]: Rows written per table.
    """
    from sqlalchemy import MetaData, Table, create_engine, delete, insert, update

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    pointer = read_latest(bundle.parent) or {}
    connect_args = {} if database_url.startswith("sqlite") else {"connect_timeout": 10}
    engine = create_engine(database_url, connect_args=connect_args)
    meta = MetaData()
    names = ("products", "zones", "zone_metrics", "localities", "locality_metrics", "cooling_assets")
    with engine.begin() as connection:
        tables = {name: Table(name, meta, autoload_with=connection) for name in names}

        zones = json.loads((bundle / "vectors" / "zones.geojson").read_text(encoding="utf-8"))
        zone_metrics = json.loads((bundle / "tables" / "zone_metrics.json").read_text(encoding="utf-8"))
        area_of = {int(r["zone_id"]): float(r["area_km2"]) for r in zone_metrics}
        zone_rows = [{"zone_id": int(f["properties"]["zone_id"]), "zone_name": f["properties"]["zone_name"],
                      "area_km2": area_of.get(int(f["properties"]["zone_id"]), 0.0),
                      "geometry_geojson": json.dumps(f["geometry"])} for f in zones["features"]]
        metric_columns = {c.name for c in tables["zone_metrics"].columns} - {"id"}
        zone_metric_rows = [{**{k: v for k, v in r.items() if k in metric_columns}, "product_version": version}
                            for r in zone_metrics]

        localities = json.loads((bundle / "vectors" / "localities.geojson").read_text(encoding="utf-8"))
        locality_rows = [{"locality_id": int(f["properties"]["locality_id"]),
                          "locality_name": f["properties"]["locality_name"],
                          "area_km2": float(f["properties"]["area_km2"]),
                          "in_extended_limit": bool(f["properties"]["in_extended_limit"]),
                          "geometry_geojson": json.dumps(f["geometry"])} for f in localities["features"]]
        locality_metric_rows = [{**r, "product_version": version} for r in
                                json.loads((bundle / "tables" / "locality_metrics.json").read_text(encoding="utf-8"))]

        assets = json.loads((bundle / "vectors" / "cooling_assets.geojson").read_text(encoding="utf-8"))
        asset_rows = [{"asset_id": f["properties"]["asset_id"], "category": f["properties"]["category"],
                       "name": (f["properties"].get("name") or None),
                       "longitude": float(f["geometry"]["coordinates"][0]),
                       "latitude": float(f["geometry"]["coordinates"][1])} for f in assets["features"]]
        asset_rows = list({r["asset_id"]: r for r in asset_rows}.values())

        for name, rows in (("zones", zone_rows), ("localities", locality_rows), ("cooling_assets", asset_rows)):
            connection.execute(delete(tables[name]))
            connection.execute(insert(tables[name]), rows)
        for name, rows in (("zone_metrics", zone_metric_rows), ("locality_metrics", locality_metric_rows)):
            connection.execute(delete(tables[name]).where(tables[name].c.product_version == version))
            connection.execute(insert(tables[name]), rows)

        products = tables["products"]
        connection.execute(update(products).values(is_latest=False))
        connection.execute(delete(products).where(products.c.version == version))
        connection.execute(insert(products), [{
            "version": version, "scene_id": manifest["scene_id"],
            "scene_date": date.fromisoformat(manifest["scene_date"]), "model_version": manifest["model_version"],
            "manifest_sha256": sha256_file(bundle / "manifest.json"),
            "created_at": datetime.fromisoformat(manifest["created_utc"]),
            "is_latest": True, "stale": bool(pointer.get("stale", False)),
        }])
    engine.dispose()
    counts = {"zones": len(zone_rows), "zone_metrics": len(zone_metric_rows), "localities": len(locality_rows),
              "locality_metrics": len(locality_metric_rows), "cooling_assets": len(asset_rows), "products": 1}
    logging.info(f"Loaded bundle {version} into database: {counts}")
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build and publish a HeatSafe-ML product bundle (Phase 9)")
    parser.add_argument("--scene-id", default=None)
    parser.add_argument("--no-tiles", action="store_true")
    parser.add_argument("--load-db", action="store_true", help="Load tables into HEATSAFE_DATABASE_URL")
    args = parser.parse_args()
    result = build_bundle(args.scene_id, with_tiles=not args.no_tiles)
    if args.load_db:
        result["database"] = load_bundle_to_database(Path(result["bundle"]), os.environ["HEATSAFE_DATABASE_URL"])
    result.pop("tiles", None)
    print(json.dumps(result, indent=2))
