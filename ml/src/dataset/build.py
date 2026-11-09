"""
HeatSafe-ML multi-scene dataset builder (Phase 5).

For every ingested Landsat scene in the training window this module:
  1. computes master-grid arrays once (terrain is shared across scenes),
  2. stores a compact per-scene cube in `ml/data/interim/scenes/<scene_id>.npz`
     (full grid: LST, indices, masks) for maps and climatology,
  3. samples trainable pixels into one modelling table
     `ml/data/processed/training_v2.parquet` with frozen spatial split columns.

Usage:
    python -m ml.src.dataset.build              # training years (D4)
    python -m ml.src.dataset.build --include-test-year   # Phase 7 only
"""

import argparse
import json
import re
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rasterio.warp import transform
from scipy.ndimage import uniform_filter

from ml.src.commons.logger import get_ml_logger
from ml.src.commons.manifest import DataManifestManager
from ml.src.dataset.splits import assign_split_columns, load_or_create_splits, load_thresholds
from ml.src.preprocess.align import load_master_grid_spec
from ml.src.preprocess.features import (
    assign_deterministic_spatial_blocks,
    compute_scene_arrays,
    compute_static_terrain,
)

logging = get_ml_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_LANDSAT_DIR = REPO_ROOT / "ml" / "data" / "raw" / "landsat"
RAW_DEM_DIR = REPO_ROOT / "ml" / "data" / "raw" / "dem"
INTERIM_DIR = REPO_ROOT / "ml" / "data" / "interim"
SCENES_DIR = INTERIM_DIR / "scenes"
PROCESSED_DIR = REPO_ROOT / "ml" / "data" / "processed"
TRAINING_TABLE = PROCESSED_DIR / "training_v2.parquet"
SCENE_INDEX = PROCESSED_DIR / "scene_index.parquet"

BAND_ALIASES = ("ST_B10", "QA_PIXEL", "QA_RADSAT", "SR_B3", "SR_B4", "SR_B5", "SR_B6")
REQUIRED_BANDS = ("ST_B10", "QA_PIXEL", "SR_B3", "SR_B4", "SR_B5", "SR_B6")
# Planetary Computer scene ids omit the USGS processing date: LC08_L2SP_144045_20240529_02_T1
SCENE_ID_PATTERN = re.compile(r"^(L[CO]0[89]_L2SP_\d{6}_(\d{8})_\d{2}_T\d)_ST_B10\.tif$")
NOMINAL_OVERPASS_UTC = "05:08:00"  # Landsat 8/9 over Nagpur (~10:00 local solar time)
FOCAL_WINDOWS = {"150m": 5, "450m": 15}  # square windows in 30 m cells


def focal_mean(values: np.ndarray, window: int) -> np.ndarray:
    """
    Mean of valid spectral-index values in a square neighbourhood around each cell.

    Cells outside [-1, 1] or non-finite are ignored; cells with no valid neighbour get NaN.

    Args:
        values (np.ndarray): 2D index raster (e.g. NDVI).
        window (int): Window edge length in cells (odd).

    Returns:
        np.ndarray: Neighbourhood mean (float32).
    """
    valid = np.isfinite(values) & (values >= -1.0) & (values <= 1.0)
    filled = np.where(valid, values, 0.0).astype(np.float64)
    value_sum = uniform_filter(filled, size=window, mode="constant", cval=0.0)
    valid_sum = uniform_filter(valid.astype(np.float64), size=window, mode="constant", cval=0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(valid_sum > 1e-9, value_sum / valid_sum, np.nan).astype(np.float32)


def discover_scenes(raw_dir: Path = RAW_LANDSAT_DIR) -> list[dict[str, Any]]:
    """
    Find complete Landsat scenes on disk and attach their acquisition times.

    Acquisition timestamps come from the data manifest; scenes ingested before
    timestamps were recorded fall back to the scene date plus the nominal overpass time.

    Args:
        raw_dir (Path): Directory holding `<scene_id>_<band>.tif` files.

    Returns:
        list[dict[str, Any]]: Sorted records with scene_id, date, acquisition_datetime, bands.
    """
    manifest_times: dict[str, str] = {}
    for record in DataManifestManager().load_all_records():
        if record.get("source") == "USGS_Landsat_C2L2" and "T" in str(record.get("acquisition_date", "")):
            manifest_times[record["scene_id"]] = record["acquisition_date"]

    scenes = []
    for st_file in sorted(raw_dir.glob("*_ST_B10.tif")):
        match = SCENE_ID_PATTERN.match(st_file.name)
        if not match:
            continue
        scene_id, yyyymmdd = match.group(1), match.group(2)
        bands = {alias: raw_dir / f"{scene_id}_{alias}.tif" for alias in BAND_ALIASES}
        missing = [b for b in REQUIRED_BANDS if not bands[b].is_file()]
        if missing:
            logging.warning(f"Scene {scene_id} incomplete (missing {missing}); skipping")
            continue
        date = datetime.strptime(yyyymmdd, "%Y%m%d").strftime("%Y-%m-%d")
        acquisition = manifest_times.get(scene_id, f"{date}T{NOMINAL_OVERPASS_UTC}Z")
        scenes.append({"scene_id": scene_id, "date": date, "acquisition_datetime": acquisition, "bands": bands})
    return sorted(scenes, key=lambda s: s["date"])


def grid_geometry() -> dict[str, np.ndarray]:
    """
    Precompute per-cell coordinates, block ids, and row/col indices for the master grid.

    Returns:
        dict[str, np.ndarray]: Flattened 'row', 'col', 'easting', 'northing', 'longitude', 'block_id'.
    """
    spec = load_master_grid_spec()
    rows, cols = np.indices(spec["shape"])
    easting = spec["min_easting"] + (cols + 0.5) * spec["cell_size"]
    northing = spec["max_northing"] - (rows + 0.5) * spec["cell_size"]
    lon, _ = transform("EPSG:32644", "EPSG:4326", easting.ravel(), northing.ravel())
    block_ids = assign_deterministic_spatial_blocks(
        easting.ravel(), northing.ravel(), spec["min_easting"], spec["min_northing"], 2000.0
    )
    return {
        "row": rows.ravel().astype(np.int16),
        "col": cols.ravel().astype(np.int16),
        "easting": easting.ravel(),
        "northing": northing.ravel(),
        "longitude": np.asarray(lon),
        "block_id": block_ids,
    }


def scene_seed(scene_id: str, base_seed: int) -> int:
    """
    Derive a stable per-scene random seed.

    Args:
        scene_id (str): Landsat scene id.
        base_seed (int): Global seed from config.

    Returns:
        int: Seed that is identical across runs and platforms.
    """
    return (zlib.crc32(scene_id.encode("utf-8")) + base_seed) % (2**32)


def save_scene_cube(path: Path, features: dict[str, np.ndarray], masks: dict[str, np.ndarray],
                    metadata: dict[str, Any], trainable: np.ndarray) -> None:
    """
    Persist one scene's full-grid arrays as a compressed .npz cube.

    Static terrain is not repeated per scene (stored once in `static_terrain.npz`).

    Args:
        path (Path): Destination file.
        features (dict[str, np.ndarray]): Feature arrays from `compute_scene_arrays`.
        masks (dict[str, np.ndarray]): Validity masks from `compute_scene_arrays`.
        metadata (dict[str, Any]): Scene metadata.
        trainable (np.ndarray): Model-1 trainable mask (bool, grid-shaped).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".tmp.npz")
    np.savez_compressed(
        tmp,
        lst=np.where(masks["valid_lst"], features["lst_celsius"], np.nan).astype(np.float32),
        ndvi=features["ndvi"].astype(np.float32),
        ndbi=features["ndbi"].astype(np.float32),
        mndwi=features["mndwi"].astype(np.float32),
        trainable=trainable,
        is_water=masks["is_water"].astype(bool),
        clear_sky=masks["clear_sky"].astype(bool),
        metadata=np.array(json.dumps(metadata)),
    )
    tmp.replace(path)


def build_dataset(include_test_year: bool = False, rebuild: bool = False) -> dict[str, Any]:
    """
    Build scene cubes, the scene index, and the sampled training table.

    Scenes outside the training window are skipped unless `include_test_year`
    (Phase 7 only). Scenes whose trainable fraction is below the configured
    minimum are kept in the index but excluded from modelling.

    Args:
        include_test_year (bool): Also process 2026 test-year scenes (Decision D4).
        rebuild (bool): Recompute scene cubes even if they already exist.

    Returns:
        dict[str, Any]: Summary with scene counts and output paths.

    Raises:
        FileNotFoundError: If no DEM tiles are available.
    """
    cfg = load_thresholds()["dataset"]
    test_year = 2026
    start, end = cfg["train_start_date"], cfg["train_end_date"]
    min_fraction = float(cfg["min_scene_trainable_fraction"])
    per_scene = int(cfg["sample_pixels_per_scene"])
    base_seed = int(cfg["random_seed"])

    dem_tiles = sorted(RAW_DEM_DIR.glob("*.tif"))
    if not dem_tiles:
        raise FileNotFoundError(f"No DEM tiles found in {RAW_DEM_DIR}")

    splits = load_or_create_splits()
    geometry = grid_geometry()
    is_holdout, fold = assign_split_columns(geometry["block_id"], splits)

    terrain = compute_static_terrain(dem_tiles)
    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        INTERIM_DIR / "static_terrain.npz",
        elevation=terrain["elevation"], slope=terrain["slope"],
        aspect=terrain["aspect"], valid_dem=terrain["valid_dem"],
    )

    index_rows: list[dict[str, Any]] = []
    samples: list[pd.DataFrame] = []
    scenes = discover_scenes()
    for scene in scenes:
        in_train = start <= scene["date"] <= end
        in_test = scene["date"].startswith(str(test_year))
        if not (in_train or (include_test_year and in_test)):
            continue
        cube_path = SCENES_DIR / f"{scene['scene_id']}.npz"
        try:
            if cube_path.is_file() and not rebuild:
                with np.load(cube_path) as cube:
                    lst = cube["lst"]
                    ndvi, ndbi, mndwi = cube["ndvi"], cube["ndbi"], cube["mndwi"]
                    trainable = cube["trainable"]
                    metadata = json.loads(str(cube["metadata"]))
            else:
                features, masks, metadata = compute_scene_arrays(
                    scene["scene_id"], scene["bands"], terrain, scene["acquisition_datetime"]
                )
                trainable = (
                    masks["valid_lst"] & masks["valid_ndvi"] & masks["valid_ndbi"]
                    & masks["valid_mndwi"] & masks["valid_dem"] & ~masks["is_water"]
                )
                save_scene_cube(cube_path, features, masks, metadata, trainable)
                lst = np.where(masks["valid_lst"], features["lst_celsius"], np.nan)
                ndvi, ndbi, mndwi = features["ndvi"], features["ndbi"], features["mndwi"]
        except Exception as error:
            logging.error(f"Error building scene {scene['scene_id']}: {error}")
            continue

        trainable_flat = trainable.ravel()
        fraction = float(trainable_flat.mean())
        usable = fraction >= min_fraction
        lst_flat = lst.ravel()
        index_rows.append({
            "scene_id": scene["scene_id"],
            "date": metadata["date"],
            "year": int(metadata["date"][:4]),
            "season": metadata["season"],
            "split": "test_year" if in_test else "train",
            "trainable_fraction": round(fraction, 4),
            "usable": usable,
            "city_mean_lst": float(np.nanmean(lst_flat[trainable_flat])) if trainable_flat.any() else np.nan,
        })
        if not usable:
            logging.warning(
                f"Scene {scene['scene_id']} trainable fraction {fraction:.2%} < {min_fraction:.0%}; excluded"
            )
            continue

        focal = {
            f"{name}_{label}": focal_mean(array, size).ravel()
            for name, array in (("ndvi", ndvi), ("ndbi", ndbi), ("mndwi", mndwi))
            for label, size in FOCAL_WINDOWS.items()
        }
        candidates = np.flatnonzero(trainable_flat)
        rng = np.random.default_rng(scene_seed(scene["scene_id"], base_seed))
        chosen = np.sort(rng.choice(candidates, size=min(per_scene, candidates.size), replace=False))
        utc_hour = float(metadata["utc_decimal"])
        samples.append(pd.DataFrame({
            "scene_id": scene["scene_id"],
            "date": metadata["date"],
            "year": np.int16(int(metadata["date"][:4])),
            "season": metadata["season"],
            "split": "test_year" if in_test else "train",
            "sin_doy": np.float32(metadata["sin_doy"]),
            "cos_doy": np.float32(metadata["cos_doy"]),
            "mean_solar_hour": ((utc_hour + geometry["longitude"][chosen] / 15.0) % 24.0).astype(np.float32),
            "row": geometry["row"][chosen],
            "col": geometry["col"][chosen],
            "easting": geometry["easting"][chosen].astype(np.float32),
            "northing": geometry["northing"][chosen].astype(np.float32),
            "block_id": geometry["block_id"][chosen],
            "is_holdout_block": is_holdout[chosen],
            "fold": fold[chosen],
            "elevation": terrain["elevation"].ravel()[chosen].astype(np.float32),
            "slope": terrain["slope"].ravel()[chosen].astype(np.float32),
            "aspect": terrain["aspect"].ravel()[chosen].astype(np.float32),
            "ndvi": ndvi.ravel()[chosen].astype(np.float32),
            "ndbi": ndbi.ravel()[chosen].astype(np.float32),
            "mndwi": mndwi.ravel()[chosen].astype(np.float32),
            **{name: values[chosen] for name, values in focal.items()},
            "lst_celsius": lst_flat[chosen].astype(np.float32),
        }))
        logging.info(
            f"Scene {scene['scene_id']} ({metadata['season']}): {fraction:.1%} trainable, {chosen.size} sampled"
        )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    index_df = pd.DataFrame(index_rows).sort_values("date").reset_index(drop=True)
    index_df.to_parquet(SCENE_INDEX, index=False)
    table = pd.concat(samples, ignore_index=True) if samples else pd.DataFrame()
    table.to_parquet(TRAINING_TABLE, index=False, compression="snappy")

    DataManifestManager().record_entry(
        source="heatsafe_dataset_v2",
        scene_id="training_v2",
        acquisition_date=f"{datetime.now().strftime('%Y-%m-%d')}T00:00:00Z",
        file_path=TRAINING_TABLE,
        metadata={
            "rows": int(len(table)),
            "scenes_used": int(index_df["usable"].sum()) if len(index_df) else 0,
            "scenes_indexed": int(len(index_df)),
            "include_test_year": include_test_year,
            "sample_pixels_per_scene": per_scene,
        },
    )
    summary = {
        "scenes_indexed": int(len(index_df)),
        "scenes_used": int(index_df["usable"].sum()) if len(index_df) else 0,
        "rows": int(len(table)),
        "training_table": str(TRAINING_TABLE),
        "scene_index": str(SCENE_INDEX),
    }
    logging.info(f"Dataset build summary: {summary}")
    return summary


def main() -> None:
    """
    Command-line entry point for the dataset builder.
    """
    parser = argparse.ArgumentParser(description="Build HeatSafe-ML multi-scene dataset (Phase 5)")
    parser.add_argument("--include-test-year", action="store_true", help="Also process 2026 scenes (Phase 7 only)")
    parser.add_argument("--rebuild", action="store_true", help="Recompute scene cubes that already exist")
    args = parser.parse_args()
    print(json.dumps(build_dataset(include_test_year=args.include_test_year, rebuild=args.rebuild), indent=2))


if __name__ == "__main__":
    main()
