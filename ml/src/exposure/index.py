"""
HeatSafe-ML Heat Exposure Index (Phase 8).

The index is a documented transform of observed Landsat land-surface temperature:
each pixel's seasonal mean LST (2019-2025 training-window scenes) is converted to
its percentile rank (0-100) among land pixels inside the NMC boundary for that season.
100 = hottest surface in the city for the season; it is a *relative, daytime surface*
measure, not air temperature and not a health-risk score on its own.

Zone scores are the mean index of the zone's pixels. Rank uncertainty comes from
resampling scenes with replacement (which clear days happened to be observed).
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rasterio.features import rasterize
from rasterio.warp import transform_geom

from ml.src.commons.logger import get_ml_logger
from ml.src.dataset.build import SCENES_DIR
from ml.src.preprocess.align import load_master_grid_spec

logging = get_ml_logger(__name__)

BOUNDARY_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "boundary"
ZONES_PATH = BOUNDARY_DIR / "nagpur_zones.geojson"
SEASONS = ("summer", "monsoon", "post-monsoon", "winter")


def rasterize_zones(zones_path: Path = ZONES_PATH, id_key: str = "zone_id",
                    name_key: str = "zone_name") -> tuple[np.ndarray, pd.DataFrame]:
    """
    Burn the administrative zones onto the master grid.

    Args:
        zones_path (Path): GeoJSON with id and name properties (EPSG:4326).
        id_key (str): Property holding the integer area id.
        name_key (str): Property holding the area name.

    Returns:
        tuple[np.ndarray, pd.DataFrame]: int16 raster of zone ids (0 = outside every zone)
        and a table with zone_id, zone_name, area_km2 (from the rasterised cells).
    """
    spec = load_master_grid_spec()
    collection = json.loads(Path(zones_path).read_text(encoding="utf-8"))
    shapes = []
    rows = []
    for feature in collection["features"]:
        zone_id = int(feature["properties"][id_key])
        shapes.append((transform_geom("EPSG:4326", spec["crs"], feature["geometry"]), zone_id))
        rows.append({"zone_id": zone_id, "zone_name": str(feature["properties"][name_key])})
    raster = rasterize(shapes, out_shape=spec["shape"], transform=spec["transform"], fill=0, dtype="int16")
    table = pd.DataFrame(rows).sort_values("zone_id").reset_index(drop=True)
    cell_km2 = (spec["cell_size"] ** 2) / 1e6
    table["area_km2"] = [round(float((raster == z).sum()) * cell_km2, 3) for z in table["zone_id"]]
    return raster, table


def percentile_rank(values: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """
    Percentile rank (0-100) of each value within a reference distribution.

    Uses the mid-rank convention so ties share one rank; NaN values stay NaN.

    Args:
        values (np.ndarray): Values to rank (any shape).
        reference (np.ndarray): Reference sample (NaN ignored).

    Returns:
        np.ndarray: float32 array shaped like `values`.

    Raises:
        ValueError: If the reference has no finite values.
    """
    ref = np.sort(np.asarray(reference, dtype=np.float64)[np.isfinite(reference)])
    if ref.size == 0:
        raise ValueError("Reference distribution is empty")
    flat = np.asarray(values, dtype=np.float64)
    below = np.searchsorted(ref, flat, side="left")
    below_or_equal = np.searchsorted(ref, flat, side="right")
    rank = 100.0 * (below + below_or_equal) / (2.0 * ref.size)
    return np.where(np.isfinite(flat), rank, np.nan).astype(np.float32)


def exposure_levels(index: np.ndarray, breaks: list[float], codes: list[str]) -> np.ndarray:
    """
    Convert index values to level codes (language-neutral; the app localises them).

    Args:
        index (np.ndarray): Heat Exposure Index values (0-100, NaN allowed).
        breaks (list[float]): Ascending cut-offs; len(codes) == len(breaks) + 1.
        codes (list[str]): Level codes from coolest to hottest.

    Returns:
        np.ndarray: Object array of codes; "no_data" where the index is NaN.

    Raises:
        ValueError: If breaks and codes do not line up.
    """
    if len(codes) != len(breaks) + 1 or sorted(breaks) != list(breaks):
        raise ValueError("level codes must be one longer than ascending breaks")
    bins = np.digitize(np.nan_to_num(index, nan=0.0), breaks, right=False)
    labels = np.asarray(codes, dtype=object)[bins]
    return np.where(np.isfinite(index), labels, "no_data")


def load_season_stack(scene_index: pd.DataFrame, season: str, pixel_index: np.ndarray, key: str = "lst",
                      scenes_dir: Path = SCENES_DIR) -> tuple[np.ndarray, list[str]]:
    """
    Load one season's scenes as a (scenes x pixels) array restricted to chosen pixels.

    Only usable training-window scenes are read; non-trainable cells (cloud, water,
    invalid) are NaN so they never contribute to a composite.

    Args:
        scene_index (pd.DataFrame): Scene index from the dataset builder.
        season (str): Season label.
        pixel_index (np.ndarray): Flat indices of the pixels to keep.
        key (str): Cube variable ("lst", "ndvi", ...).
        scenes_dir (Path): Folder of per-scene cubes.

    Returns:
        tuple[np.ndarray, list[str]]: float32 stack and the scene ids in row order.
    """
    chosen = scene_index[(scene_index["season"] == season) & scene_index["usable"] & (scene_index["split"] == "train")]
    scene_ids = list(chosen["scene_id"])
    stack = np.full((len(scene_ids), pixel_index.size), np.nan, dtype=np.float32)
    for row, scene_id in enumerate(scene_ids):
        with np.load(scenes_dir / f"{scene_id}.npz") as cube:
            values = cube[key].ravel()[pixel_index].astype(np.float32)
            trainable = cube["trainable"].ravel()[pixel_index]
        stack[row] = np.where(trainable & np.isfinite(values), values, np.nan)
    return stack, scene_ids


def composite_mean(stack: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
    """
    Per-pixel mean over scenes, ignoring NaN, with optional integer scene weights.

    Args:
        stack (np.ndarray): (scenes x pixels) array.
        weights (np.ndarray | None): Times each scene is counted (bootstrap multiplicities).

    Returns:
        np.ndarray: Mean per pixel (NaN where no scene observed the pixel).
    """
    valid = np.isfinite(stack)
    w = np.ones(stack.shape[0], dtype=np.float64) if weights is None else np.asarray(weights, dtype=np.float64)
    total = (np.where(valid, stack, 0.0) * w[:, None]).sum(axis=0)
    count = (valid * w[:, None]).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, total / count, np.nan)


def zone_means(values: np.ndarray, zone_of_pixel: np.ndarray, zone_ids: list[int]) -> np.ndarray:
    """
    Mean of finite pixel values per zone.

    Args:
        values (np.ndarray): Value per pixel.
        zone_of_pixel (np.ndarray): Zone id per pixel.
        zone_ids (list[int]): Zones to report, in output order.

    Returns:
        np.ndarray: Mean per zone (NaN for a zone with no finite pixels).
    """
    finite = np.isfinite(values)
    out = np.full(len(zone_ids), np.nan)
    for position, zone_id in enumerate(zone_ids):
        member = finite & (zone_of_pixel == zone_id)
        if member.any():
            out[position] = float(values[member].mean())
    return out


def bootstrap_zone_exposure(stack: np.ndarray, zone_of_pixel: np.ndarray, zone_ids: list[int],
                            n_resamples: int, seed: int) -> np.ndarray:
    """
    Zone exposure under scene resampling (which clear days were observed).

    Each replicate redraws scenes with replacement, rebuilds the seasonal mean,
    re-ranks every pixel, and averages the index per zone.

    Args:
        stack (np.ndarray): (scenes x pixels) LST for pixels inside the reference area.
        zone_of_pixel (np.ndarray): Zone id per pixel.
        zone_ids (list[int]): Zones in output order.
        n_resamples (int): Number of bootstrap replicates.
        seed (int): Random seed.

    Returns:
        np.ndarray: (n_resamples x zones) zone exposure values.
    """
    rng = np.random.default_rng(seed)
    n_scenes = stack.shape[0]
    replicates = np.empty((n_resamples, len(zone_ids)), dtype=np.float64)
    # Precompute once so each replicate is two matrix-vector products.
    valid = np.isfinite(stack).astype(np.float32)
    filled = np.where(valid > 0, stack, 0.0).astype(np.float32)
    for b in range(n_resamples):
        weights = np.bincount(rng.integers(0, n_scenes, n_scenes), minlength=n_scenes).astype(np.float32)
        count = weights @ valid
        with np.errstate(invalid="ignore", divide="ignore"):
            mean_lst = np.where(count > 0, (weights @ filled) / count, np.nan)
        replicates[b] = zone_means(percentile_rank(mean_lst, mean_lst), zone_of_pixel, zone_ids)
    return replicates


def season_exposure(scene_index: pd.DataFrame, season: str, zone_raster: np.ndarray, zone_ids: list[int],
                    n_resamples: int, seed: int) -> dict[str, Any]:
    """
    Exposure index raster, zone scores, and bootstrap replicates for one season.

    Args:
        scene_index (pd.DataFrame): Scene index from the dataset builder.
        season (str): Season label.
        zone_raster (np.ndarray): Zone id raster (0 = outside NMC zones).
        zone_ids (list[int]): Zones in output order.
        n_resamples (int): Bootstrap replicates.
        seed (int): Random seed.

    Returns:
        dict[str, Any]: index_raster (grid, NaN outside the city or without data), mean_lst_raster,
        zone_exposure, zone_mean_lst, replicates, scenes.
    """
    inside = np.flatnonzero(zone_raster.ravel() > 0)
    zone_of_pixel = zone_raster.ravel()[inside]
    stack, scene_ids = load_season_stack(scene_index, season, inside)
    mean_lst = composite_mean(stack)
    index = percentile_rank(mean_lst, mean_lst)

    index_raster = np.full(zone_raster.size, np.nan, dtype=np.float32)
    lst_raster = np.full(zone_raster.size, np.nan, dtype=np.float32)
    index_raster[inside] = index
    lst_raster[inside] = mean_lst
    logging.info(f"Exposure index for {season}: {len(scene_ids)} scenes, {np.isfinite(index).sum():,} city pixels")
    return {
        "index_raster": index_raster.reshape(zone_raster.shape),
        "mean_lst_raster": lst_raster.reshape(zone_raster.shape),
        "zone_exposure": zone_means(index, zone_of_pixel, zone_ids),
        "zone_mean_lst": zone_means(mean_lst, zone_of_pixel, zone_ids),
        "replicates": bootstrap_zone_exposure(stack, zone_of_pixel, zone_ids, n_resamples, seed),
        "scenes": scene_ids,
    }
