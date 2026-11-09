"""
HeatSafe-ML first working result (Phase 5): seasonal LST maps and Gi* hotspots.

Outputs (git-ignored, hashes in the manifest):
  ml/data/processed/maps/lst_<season>_<start>_<end>.tif   per-pixel mean LST (°C), EPSG:32644, 30 m
  ml/data/processed/maps/lst_<season>_<start>_<end>.png   preview with NMC boundary
  ml/data/processed/maps/hotspots_<season>.geojson       Gi* hot/cold clusters, EPSG:4326

Usage:
    python -m ml.src.eda.maps
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_geom
from scipy.ndimage import convolve
from scipy.stats import norm

from ml.src.commons.logger import get_ml_logger
from ml.src.commons.manifest import DataManifestManager
from ml.src.dataset.build import PROCESSED_DIR, SCENE_INDEX, SCENES_DIR
from ml.src.dataset.splits import load_thresholds
from ml.src.preprocess.align import load_master_grid_spec

logging = get_ml_logger(__name__)

MAPS_DIR = PROCESSED_DIR / "maps"
BOUNDARY_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "boundary" / "nagpur_nmc.geojson"
SEASONS = ("summer", "monsoon", "post-monsoon", "winter")


def seasonal_mean_lst(scene_index: pd.DataFrame, season: str, scenes_dir: Path = SCENES_DIR) -> dict[str, Any]:
    """
    Average valid land-surface temperature per pixel over all usable scenes of one season.

    Only training-window scenes are used (the 2026 test year never enters EDA).
    Water and cloud pixels are excluded through each scene's trainable mask.

    Args:
        scene_index (pd.DataFrame): Output of the dataset builder's scene index.
        season (str): One of SEASONS.
        scenes_dir (Path): Directory of per-scene .npz cubes.

    Returns:
        dict[str, Any]: 'mean' (°C, NaN where never observed), 'count' (observations per pixel),
        and 'scenes' (scene ids used).
    """
    chosen = scene_index[(scene_index["season"] == season) & scene_index["usable"] & (scene_index["split"] == "train")]
    shape = load_master_grid_spec()["shape"]
    total = np.zeros(shape, dtype=np.float64)
    count = np.zeros(shape, dtype=np.int32)
    for scene_id in chosen["scene_id"]:
        with np.load(scenes_dir / f"{scene_id}.npz") as cube:
            valid = cube["trainable"] & np.isfinite(cube["lst"])
            total[valid] += cube["lst"][valid]
            count[valid] += 1
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(count > 0, total / count, np.nan).astype(np.float32)
    return {"mean": mean, "count": count, "scenes": list(chosen["scene_id"])}


def getis_ord_gi_star(values: np.ndarray, radius_cells: int, min_neighbours: int) -> np.ndarray:
    """
    Compute the Getis-Ord Gi* z-score on a raster with binary distance-band weights.

    Neighbourhood sums use a circular convolution kernel (the cell itself included,
    as Gi* requires). NaN cells are ignored; cells with fewer than `min_neighbours`
    valid neighbours return NaN.

    Args:
        values (np.ndarray): 2D raster (NaN = no data).
        radius_cells (int): Distance band in cells.
        min_neighbours (int): Minimum valid cells in the band for a z-score.

    Returns:
        np.ndarray: Gi* z-scores (float32), positive = hot cluster, negative = cold cluster.
    """
    yy, xx = np.mgrid[-radius_cells:radius_cells + 1, -radius_cells:radius_cells + 1]
    kernel = ((yy**2 + xx**2) <= radius_cells**2).astype(np.float64)

    valid = np.isfinite(values)
    x = np.where(valid, values, 0.0).astype(np.float64)
    n = valid.sum()
    x_bar = x[valid].mean()
    s = np.sqrt((x[valid] ** 2).mean() - x_bar**2)

    w_sum = convolve(valid.astype(np.float64), kernel, mode="constant", cval=0.0)
    wx_sum = convolve(x, kernel, mode="constant", cval=0.0)
    w_sq = w_sum  # binary weights: sum(w^2) == sum(w)
    denominator = s * np.sqrt((n * w_sq - w_sum**2) / (n - 1))
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (wx_sum - x_bar * w_sum) / denominator
    z[(~valid) | (w_sum < min_neighbours) | (denominator <= 0)] = np.nan
    return z.astype(np.float32)


def fdr_z_threshold(z: np.ndarray, alpha: float) -> float:
    """
    Benjamini-Hochberg false-discovery-rate threshold for two-sided Gi* z-scores.

    Neighbouring 30 m cells are strongly autocorrelated, so an uncorrected p < 0.05
    flags most of the city. FDR control keeps the expected share of false clusters at `alpha`.

    Args:
        z (np.ndarray): Gi* z-scores (NaN ignored).
        alpha (float): Target false discovery rate, e.g. 0.05.

    Returns:
        float: |z| cut-off; +inf when nothing survives the correction.
    """
    finite = np.abs(z[np.isfinite(z)]).astype(np.float64)
    if finite.size == 0:
        return float("inf")
    p_sorted = np.sort(2.0 * norm.sf(finite))
    ranks = np.arange(1, p_sorted.size + 1)
    passing = np.flatnonzero(p_sorted <= alpha * ranks / p_sorted.size)
    if passing.size == 0:
        return float("inf")
    return float(norm.isf(p_sorted[passing[-1]] / 2.0))


def hotspots_to_geojson(z: np.ndarray, z_threshold: float, season: str) -> dict[str, Any]:
    """
    Polygonise significant Gi* clusters into a WGS84 GeoJSON FeatureCollection.

    Args:
        z (np.ndarray): Gi* z-score raster on the master grid.
        z_threshold (float): |z| above which a cell is significant (1.96 → p < 0.05).
        season (str): Season label stored on each feature.

    Returns:
        dict[str, Any]: GeoJSON with 'hot' and 'cold' cluster polygons.
    """
    spec = load_master_grid_spec()
    classes = np.zeros(z.shape, dtype=np.int16)
    classes[z >= z_threshold] = 1
    classes[z <= -z_threshold] = -1
    features = []
    for geometry, value in shapes(classes, mask=classes != 0, transform=spec["transform"], connectivity=8):
        geom_wgs84 = transform_geom(spec["crs"], "EPSG:4326", geometry)
        features.append({
            "type": "Feature",
            "geometry": geom_wgs84,
            "properties": {
                "cluster": "hot" if value > 0 else "cold",
                "season": season,
                "z_cutoff": round(z_threshold, 3),
                "confidence": "FDR-corrected, q<0.05",
            },
        })
    return {"type": "FeatureCollection", "features": features}


def write_geotiff(path: Path, array: np.ndarray, tags: dict[str, str]) -> None:
    """
    Write a float32 single-band GeoTIFF on the master grid with descriptive tags.

    Args:
        path (Path): Output file.
        array (np.ndarray): 2D raster.
        tags (dict[str, str]): Metadata stored in the GeoTIFF.
    """
    spec = load_master_grid_spec()
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff", "height": array.shape[0], "width": array.shape[1], "count": 1,
        "dtype": "float32", "crs": spec["crs"], "transform": spec["transform"], "nodata": np.nan,
        "tiled": True, "blockxsize": 256, "blockysize": 256, "compress": "deflate",
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array.astype(np.float32), 1)
        dst.update_tags(**tags)


def write_preview_png(path: Path, array: np.ndarray, title: str, vmin: float, vmax: float) -> None:
    """
    Render a map preview PNG with a colour bar and the NMC boundary outline.

    Args:
        path (Path): Output PNG.
        array (np.ndarray): LST raster (°C).
        title (str): Figure title.
        vmin (float): Lower colour limit.
        vmax (float): Upper colour limit.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    spec = load_master_grid_spec()
    extent = (spec["min_easting"], spec["max_easting"], spec["min_northing"], spec["max_northing"])
    fig, ax = plt.subplots(figsize=(8, 7), dpi=120)
    image = ax.imshow(array, cmap="inferno", vmin=vmin, vmax=vmax, extent=extent)
    if BOUNDARY_PATH.is_file():
        boundary = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
        for feature in boundary.get("features", [boundary]):
            geom = transform_geom("EPSG:4326", spec["crs"], feature.get("geometry", feature))
            polygons = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
            for polygon in polygons:
                ring = np.asarray(polygon[0])
                ax.plot(ring[:, 0], ring[:, 1], color="cyan", linewidth=0.8)
    fig.colorbar(image, ax=ax, label="Land surface temperature (°C)", shrink=0.8)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Easting (m, EPSG:32644)")
    ax.set_ylabel("Northing (m)")
    fig.text(
        0.01, 0.01,
        "Landsat 8/9 C2 L2 ST_B10 | 30 m analytical grid (thermal native ~100 m) | surface, not air, temperature",
        fontsize=6,
    )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def build_first_working_result() -> dict[str, Any]:
    """
    Produce seasonal mean LST maps and Gi* hotspot layers for every season with data.

    Returns:
        dict[str, Any]: Per-season summary (scenes, date range, coverage, cluster counts, outputs).
    """
    cfg = load_thresholds()
    eda_cfg = cfg["eda"]
    start = cfg["dataset"]["train_start_date"][:4]
    end = cfg["dataset"]["train_end_date"][:4]
    cell = load_master_grid_spec()["cell_size"]
    radius_cells = int(round(float(eda_cfg["gi_star_radius_meters"]) / cell))

    index = pd.read_parquet(SCENE_INDEX)
    manifest = DataManifestManager()
    summary: dict[str, Any] = {}
    composites = {s: seasonal_mean_lst(index, s) for s in SEASONS}
    finite = [c["mean"][np.isfinite(c["mean"])] for c in composites.values() if np.isfinite(c["mean"]).any()]
    vmin = float(np.percentile(np.concatenate(finite), 1)) if finite else 20.0
    vmax = float(np.percentile(np.concatenate(finite), 99)) if finite else 50.0

    for season, composite in composites.items():
        if not composite["scenes"]:
            logging.warning(f"No usable scenes for season {season}; skipping map")
            continue
        dates = index.set_index("scene_id").loc[composite["scenes"], "date"]
        coverage = float(np.isfinite(composite["mean"]).mean())
        tags = {
            "variable": "mean land surface temperature (deg C) — NOT air temperature",
            "season": season,
            "scene_count": str(len(composite["scenes"])),
            "date_range": f"{dates.min()} to {dates.max()}",
            "scenes": ",".join(composite["scenes"]),
            "crs": "EPSG:32644",
            "resolution": "30 m analytical grid; Landsat thermal native ~100 m (Decision D6)",
            "masking": (
                "QA_PIXEL fill/cloud/shadow/cirrus/snow removed; water excluded; "
                "indices outside [-1,1] excluded"
            ),
        }
        tif = MAPS_DIR / f"lst_{season}_{start}_{end}.tif"
        write_geotiff(tif, composite["mean"], tags)
        write_geotiff(MAPS_DIR / f"lst_{season}_{start}_{end}_count.tif", composite["count"].astype(np.float32),
                      {"variable": "number of valid observations per pixel", "season": season})
        write_preview_png(tif.with_suffix(".png"), composite["mean"],
                          f"Nagpur mean LST — {season} {start}–{end} ({len(composite['scenes'])} scenes)", vmin, vmax)

        z = getis_ord_gi_star(composite["mean"], radius_cells, int(eda_cfg["gi_star_min_valid_neighbours"]))
        z_cut = max(float(eda_cfg["gi_star_z_threshold"]), fdr_z_threshold(z, float(eda_cfg["gi_star_fdr_alpha"])))
        hotspots = hotspots_to_geojson(z, z_cut, season)
        geojson_path = MAPS_DIR / f"hotspots_{season}.geojson"
        geojson_path.write_text(json.dumps(hotspots), encoding="utf-8")

        for path, kind in ((tif, "seasonal_mean_lst"), (geojson_path, "gi_star_hotspots")):
            manifest.record_entry(
                source="heatsafe_eda_v1", scene_id=path.stem,
                acquisition_date=f"{dates.max()}T00:00:00Z", file_path=path,
                metadata={"type": kind, "season": season, "scene_count": len(composite["scenes"])},
            )
        n_hot = sum(f["properties"]["cluster"] == "hot" for f in hotspots["features"])
        summary[season] = {
            "scenes": len(composite["scenes"]),
            "date_range": tags["date_range"],
            "pixel_coverage": round(coverage, 4),
            "city_mean_lst": round(float(np.nanmean(composite["mean"])), 2),
            "p05_p95_lst": [round(float(np.nanpercentile(composite["mean"], q)), 2) for q in (5, 95)],
            "hot_clusters": n_hot,
            "cold_clusters": len(hotspots["features"]) - n_hot,
            "gi_star_z_cutoff_fdr": round(z_cut, 3),
            "hot_area_share": round(float(np.mean(z[np.isfinite(z)] >= z_cut)), 4),
            "cold_area_share": round(float(np.mean(z[np.isfinite(z)] <= -z_cut)), 4),
            "outputs": [str(tif), str(tif.with_suffix(".png")), str(geojson_path)],
        }
        logging.info(f"Season {season}: {summary[season]}")

    (MAPS_DIR / "maps_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build_first_working_result(), indent=2))
