"""
HeatSafe-ML Feature Engineering & Spatial Partitioning Engine.
Computes spectral indices (NDVI, NDBI, MNDWI), Horn's (1981) 3x3 finite-difference terrain derivatives,
deterministic origin-anchored 2 km spatial cross-validation blocks (Decision D5),
per-pixel mean local solar time encodings, and decoupled feature validity Parquet export.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from rasterio.warp import transform
import yaml

from ml.src.commons.logger import get_ml_logger
from ml.src.commons.manifest import DataManifestManager
from ml.src.preprocess.align import (
    load_master_grid_spec,
    reproject_to_master_grid,
    decode_landsat_qa_pixel,
    decode_landsat_qa_radsat,
    scale_landsat_lst,
    scale_surface_reflectance,
)

logger = get_ml_logger(__name__)


def compute_spectral_indices(
    green: np.ndarray,
    red: np.ndarray,
    nir: np.ndarray,
    swir: np.ndarray,
) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """
    Compute Normalized Difference Vegetation Index (NDVI), Normalized Difference Built-Up Index (NDBI),
    and Modified Normalized Difference Water Index (MNDWI) with division-by-zero protection.

    Formulas:
        NDVI = (NIR - Red) / (NIR + Red)
        NDBI = (SWIR - NIR) / (SWIR + NIR)
        MNDWI = (Green - SWIR) / (Green + SWIR)

    Validity Principle:
        Each index retains its own independent validity mask. An index is valid if:
        - The denominator absolute value exceeds 1e-6 (protecting against zero or near-zero division).
        - The resulting value is finite (not NaN or Inf).
        - The physical value lies within the valid theoretical range [-1.0, 1.0].

    Returns:
        Dict mapping index name to Tuple of (index_array, validity_mask).
    """
    results: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

    index_specs = [
        ("ndvi", nir, red),
        ("ndbi", swir, nir),
        ("mndwi", green, swir),
    ]

    for name, band_a, band_b in index_specs:
        denom = band_a.astype(np.float64) + band_b.astype(np.float64)
        numer = band_a.astype(np.float64) - band_b.astype(np.float64)

        denom_valid = np.abs(denom) > 1e-6
        index_arr = np.full(band_a.shape, np.nan, dtype=np.float32)

        # Compute index where denominator is safe
        safe_mask = denom_valid & np.isfinite(numer) & np.isfinite(denom)
        index_arr[safe_mask] = (numer[safe_mask] / denom[safe_mask]).astype(np.float32)

        # Physical validity criteria: [-1.0, 1.0] and finite
        valid_mask = safe_mask & (index_arr >= -1.0) & (index_arr <= 1.0)

        results[name] = (index_arr, valid_mask)

    return results


def compute_horn_terrain_derivatives(
    dem: np.ndarray,
    cell_size: float = 30.0,
    nodata_val: float = -9999.0,
) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """
    Compute slope and aspect using Horn's (1981) exact 8-neighbor weighted finite-difference algorithm.

    Algorithm (Horn 1981):
        Given a 3x3 window around center pixel z_c:
            [z_tl, z_t, z_tr]
            [z_l,  z_c, z_r ]
            [z_bl, z_b, z_br]
        where row index increases Southwards (top row = North, bottom row = South)
        and column index increases Eastwards (left col = West, right col = East).

        Weighted gradients:
            dz_dx = ((z_tr + 2*z_r + z_br) - (z_tl + 2*z_l + z_bl)) / (8 * cell_size)
            dy    = ((z_bl + 2*z_b + z_br) - (z_tl + 2*z_t + z_tr)) / (8 * cell_size)

        Slope:
            Slope_deg = arctan(sqrt(dz_dx^2 + dy^2)) * 180 / pi  (range: [0, 90])

        Aspect:
            Downhill gradient vector is (-dz_dx, dy).
            Aspect_deg = (arctan2(-dz_dx, dy) * 180 / pi) % 360  (range: [0, 360])
            For completely flat terrain (dz_dx == 0 and dy == 0), aspect is assigned -1.0.

    NoData & Boundary Policy:
        If the center cell or any of the 8 neighbors is NaN, infinite, or equal to nodata_val,
        the center cell slope and aspect are explicitly assigned NaN with validity False.
        Perimeter border cells (row 0, row nrows-1, col 0, col ncols-1) where the 3x3 window
        is incomplete are assigned NaN with validity False.

    Returns:
        Dict containing:
            - 'slope': (slope_arr, valid_slope_mask)
            - 'aspect': (aspect_arr, valid_aspect_mask)
            - 'elevation': (dem_arr, valid_elevation_mask)
            - 'valid_dem': Combined boolean mask (valid elevation, slope, and aspect).
    """
    nrows, ncols = dem.shape
    slope = np.full((nrows, ncols), np.nan, dtype=np.float32)
    aspect = np.full((nrows, ncols), np.nan, dtype=np.float32)

    # Valid elevation mask for raw DEM
    valid_elevation = np.isfinite(dem) & (dem != nodata_val)

    if nrows >= 3 and ncols >= 3:
        # 3x3 Slices for interior cells (1 to nrows-2, 1 to ncols-2)
        z_tl = dem[:-2, :-2]
        z_t  = dem[:-2, 1:-1]
        z_tr = dem[:-2, 2:]
        z_l  = dem[1:-1, :-2]
        z_c  = dem[1:-1, 1:-1]
        z_r  = dem[1:-1, 2:]
        z_bl = dem[2:, :-2]
        z_b  = dem[2:, 1:-1]
        z_br = dem[2:, 2:]

        # Full 8-neighbor validity check
        valid_window = (
            np.isfinite(z_tl) & (z_tl != nodata_val) &
            np.isfinite(z_t)  & (z_t  != nodata_val) &
            np.isfinite(z_tr) & (z_tr != nodata_val) &
            np.isfinite(z_l)  & (z_l  != nodata_val) &
            np.isfinite(z_c)  & (z_c  != nodata_val) &
            np.isfinite(z_r)  & (z_r  != nodata_val) &
            np.isfinite(z_bl) & (z_bl != nodata_val) &
            np.isfinite(z_b)  & (z_b  != nodata_val) &
            np.isfinite(z_br) & (z_br != nodata_val)
        )

        dz_dx = np.zeros_like(z_c, dtype=np.float64)
        dy = np.zeros_like(z_c, dtype=np.float64)

        dz_dx[valid_window] = (
            (z_tr[valid_window] + 2.0 * z_r[valid_window] + z_br[valid_window])
            - (z_tl[valid_window] + 2.0 * z_l[valid_window] + z_bl[valid_window])
        ) / (8.0 * cell_size)

        dy[valid_window] = (
            (z_bl[valid_window] + 2.0 * z_b[valid_window] + z_br[valid_window])
            - (z_tl[valid_window] + 2.0 * z_t[valid_window] + z_tr[valid_window])
        ) / (8.0 * cell_size)

        # Slope calculation
        grad_mag = np.sqrt(dz_dx**2 + dy**2)
        slope_interior = np.full_like(z_c, np.nan, dtype=np.float32)
        slope_interior[valid_window] = np.degrees(np.arctan(grad_mag[valid_window])).astype(np.float32)

        # Aspect calculation (downhill azimuth in degrees clockwise from North)
        aspect_interior = np.full_like(z_c, np.nan, dtype=np.float32)
        flat_mask = valid_window & np.isclose(dz_dx, 0.0) & np.isclose(dy, 0.0)
        non_flat_mask = valid_window & ~flat_mask

        aspect_interior[flat_mask] = -1.0
        aspect_interior[non_flat_mask] = (
            np.degrees(np.arctan2(-dz_dx[non_flat_mask], dy[non_flat_mask])) % 360.0
        ).astype(np.float32)

        # Assign back into full grid
        slope[1:-1, 1:-1] = slope_interior
        aspect[1:-1, 1:-1] = aspect_interior

    valid_slope = np.isfinite(slope) & (slope >= 0.0) & (slope <= 90.0)
    valid_aspect = np.isfinite(aspect) & ((aspect == -1.0) | ((aspect >= 0.0) & (aspect <= 360.0)))
    valid_dem = valid_elevation & valid_slope & valid_aspect

    return {
        "slope": (slope, valid_slope),
        "aspect": (aspect, valid_aspect),
        "elevation": (dem.astype(np.float32), valid_elevation),
        "valid_dem": valid_dem,
    }


def assign_deterministic_spatial_blocks(
    easting: np.ndarray,
    northing: np.ndarray,
    origin_easting: float = 285960.0,
    origin_northing: float = 2328030.0,
    block_size: float = 2000.0,
) -> np.ndarray:
    """
    Assign deterministic 2 km spatial block identifiers relative to the master grid origin (Decision D5).

    Formula:
        col_idx = floor((easting - origin_easting) / block_size)
        row_idx = floor((northing - origin_northing) / block_size)
        block_id = f"B_{col_idx:02d}_{row_idx:02d}"

    Edge Invariant:
        Coordinates on block boundaries are deterministically assigned to the upper block
        via standard floor rounding, avoiding boundary ambiguity or negative indices within
        the master grid extent.

    Returns:
        1D numpy array of string block identifiers of same length as input coordinates.
    """
    col_idx = np.floor((easting - origin_easting) / block_size).astype(int)
    row_idx = np.floor((northing - origin_northing) / block_size).astype(int)

    # Generate deterministic string identifiers
    block_ids = np.array(
        [f"B_{c:02d}_{r:02d}" for c, r in zip(col_idx.flat, row_idx.flat)]
    )
    return block_ids


def compute_pixel_mean_local_solar_time(
    utc_datetime_str: str,
    lon_deg: np.ndarray,
) -> Dict[str, Any]:
    """
    Compute per-pixel Mean Local Solar Time (MLST) across the study area and temporal encodings.

    Scientific Distinction & Formulation:
        - Indian Standard Time (IST) is fixed civil time: IST = UTC + 5:30 (based on 82.5°E).
        - Mean Local Solar Time (MLST) accounts for actual solar position based on pixel longitude:
            MLST = UTC_decimal + (Longitude° / 15°/hr)
        - Note: This represents Mean Local Solar Time. The Equation of Time (EOT) correction
          for apparent solar time is not applied in this phase.
        - Landsat overpasses Nagpur nominally at ~10:00 AM mean local solar time (~10:14–10:18 AM IST).

    Cyclical Day-of-Year Encoding:
        sin_doy = sin(2 * pi * DOY / 365.25)
        cos_doy = cos(2 * pi * DOY / 365.25)

    Seasonal Classification (Decision D7):
        - Summer: March, April, May (Months 3-5)
        - Monsoon: June, July, August, September (Months 6-9)
        - Post-Monsoon: October, November (Months 10-11)
        - Winter: December, January, February (Months 12, 1, 2)

    Returns:
        Dict containing:
            - 'mean_solar_time_hours': Array or scalar of MLST in decimal hours [0, 24).
            - 'utc_decimal': UTC time in decimal hours.
            - 'ist_decimal': Indian Standard Time in decimal hours.
            - 'date': YYYY-MM-DD string.
            - 'doy': Integer day of year.
            - 'sin_doy': Cyclical sine DOY encoding.
            - 'cos_doy': Cyclical cosine DOY encoding.
            - 'season': Season string ('summer', 'monsoon', 'post-monsoon', 'winter').
    """
    clean_str = utc_datetime_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_str)

    utc_decimal = (
        dt.hour
        + dt.minute / 60.0
        + dt.second / 3600.0
        + dt.microsecond / 3.6e9
    )
    ist_decimal = (utc_decimal + 5.5) % 24.0

    mean_solar_time_hours = (utc_decimal + lon_deg / 15.0) % 24.0

    doy = dt.timetuple().tm_yday
    sin_doy = float(np.sin(2.0 * np.pi * doy / 365.25))
    cos_doy = float(np.cos(2.0 * np.pi * doy / 365.25))

    month = dt.month
    if month in (3, 4, 5):
        season = "summer"
    elif month in (6, 7, 8, 9):
        season = "monsoon"
    elif month in (10, 11):
        season = "post-monsoon"
    else:
        season = "winter"

    return {
        "mean_solar_time_hours": mean_solar_time_hours,
        "utc_decimal": utc_decimal,
        "ist_decimal": ist_decimal,
        "date": dt.strftime("%Y-%m-%d"),
        "doy": doy,
        "sin_doy": sin_doy,
        "cos_doy": cos_doy,
        "season": season,
    }


def export_feature_table(
    features_dict: Dict[str, np.ndarray],
    masks_dict: Dict[str, np.ndarray],
    metadata: Dict[str, Any],
    out_path: Path,
    manifest_manager: Optional[DataManifestManager] = None,
) -> Path:
    """
    Export processed features and decoupled validity masks onto a columnar Parquet table.

    Decoupled Feature Validity Principle:
        Every feature retains its own independent validity mask (valid_lst, valid_ndvi, valid_dem,
        is_water, clear_sky). Rather than a single destructive filter that irreversibly drops
        pixels with cloud or water, all rows on the master grid are preserved.
        An explicit boolean selection column `trainable_terrestrial_lst` is provided for standard
        Model 1 terrestrial training:
            trainable_terrestrial_lst = valid_lst & valid_ndvi & valid_ndbi & valid_mndwi & valid_dem & ~is_water

    Args:
        features_dict: Dict of 2D feature arrays (elevation, slope, aspect, ndvi, ndbi, mndwi, lst_celsius).
        masks_dict: Dict of boolean masks (valid_dem, valid_ndvi, valid_ndbi, valid_mndwi, valid_lst, is_water, clear_sky).
        metadata: Dict containing scene_id, date, season, sin_doy, cos_doy, utc_hour, mean_solar_hour, etc.
        out_path: Destination path for .parquet file.
        manifest_manager: Optional DataManifestManager to register the asset.

    Returns:
        Path to written Parquet file.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    grid_spec = load_master_grid_spec()
    nrows, ncols = grid_spec["shape"]
    min_easting = grid_spec["min_easting"]
    max_northing = grid_spec["max_northing"]
    cell_size = grid_spec["cell_size"]

    # Compute pixel center coordinates across master grid
    rows, cols = np.indices((nrows, ncols))
    easting_2d = min_easting + (cols + 0.5) * cell_size
    northing_2d = max_northing - (rows + 0.5) * cell_size

    # Reproject pixel centers to WGS84 (lon, lat)
    easting_flat = easting_2d.ravel()
    northing_flat = northing_2d.ravel()
    lon_flat, lat_flat = transform("EPSG:32644", "EPSG:4326", easting_flat, northing_flat)

    # Compute deterministic spatial blocks (Decision D5)
    block_ids = assign_deterministic_spatial_blocks(
        easting=easting_flat,
        northing=northing_flat,
        origin_easting=min_easting,
        origin_northing=grid_spec["min_northing"],
        block_size=2000.0,
    )

    # Construct pixel identifiers
    pixel_ids = [f"P_{r:03d}_{c:03d}" for r, c in zip(rows.ravel(), cols.ravel())]

    # Mean solar hour per pixel
    utc_hour = float(metadata.get("utc_decimal", 5.0))
    mean_solar_hour = ((utc_hour + np.array(lon_flat) / 15.0) % 24.0).astype(np.float32)

    # Extract feature values
    elevation = features_dict["elevation"].ravel().astype(np.float32)
    slope = features_dict["slope"].ravel().astype(np.float32)
    aspect = features_dict["aspect"].ravel().astype(np.float32)
    ndvi = features_dict["ndvi"].ravel().astype(np.float32)
    ndbi = features_dict["ndbi"].ravel().astype(np.float32)
    mndwi = features_dict["mndwi"].ravel().astype(np.float32)
    lst_celsius = features_dict["lst_celsius"].ravel().astype(np.float32)

    # Extract independent validity masks
    valid_dem = masks_dict["valid_dem"].ravel().astype(bool)
    valid_ndvi = masks_dict["valid_ndvi"].ravel().astype(bool)
    valid_ndbi = masks_dict["valid_ndbi"].ravel().astype(bool)
    valid_mndwi = masks_dict["valid_mndwi"].ravel().astype(bool)
    valid_lst = masks_dict["valid_lst"].ravel().astype(bool)
    is_water = masks_dict.get("is_water", np.zeros(len(pixel_ids), dtype=bool)).ravel().astype(bool)
    clear_sky = masks_dict.get("clear_sky", np.ones(len(pixel_ids), dtype=bool)).ravel().astype(bool)

    # Explicit Model 1 terrestrial training selection
    trainable_terrestrial_lst = (
        valid_lst
        & valid_ndvi
        & valid_ndbi
        & valid_mndwi
        & valid_dem
        & (~is_water)
    )

    n_rows = len(pixel_ids)
    df = pd.DataFrame({
        "pixel_id": pixel_ids,
        "scene_id": [str(metadata.get("scene_id", "unknown"))] * n_rows,
        "date": [str(metadata.get("date", "unknown"))] * n_rows,
        "season": [str(metadata.get("season", "unknown"))] * n_rows,
        "easting": easting_flat.astype(np.float64),
        "northing": northing_flat.astype(np.float64),
        "longitude": np.array(lon_flat, dtype=np.float64),
        "latitude": np.array(lat_flat, dtype=np.float64),
        "block_id": block_ids,
        "sin_doy": np.full(n_rows, metadata.get("sin_doy", 0.0), dtype=np.float32),
        "cos_doy": np.full(n_rows, metadata.get("cos_doy", 0.0), dtype=np.float32),
        "utc_hour": np.full(n_rows, utc_hour, dtype=np.float32),
        "mean_solar_hour": mean_solar_hour,
        "elevation": elevation,
        "slope": slope,
        "aspect": aspect,
        "ndvi": ndvi,
        "ndbi": ndbi,
        "mndwi": mndwi,
        "lst_celsius": lst_celsius,
        "valid_dem": valid_dem,
        "valid_ndvi": valid_ndvi,
        "valid_ndbi": valid_ndbi,
        "valid_mndwi": valid_mndwi,
        "valid_lst": valid_lst,
        "is_water": is_water,
        "clear_sky": clear_sky,
        "trainable_terrestrial_lst": trainable_terrestrial_lst,
    })

    df.to_parquet(out_path, index=False, engine="pyarrow", compression="snappy")
    logger.info(
        f"Exported {len(df)} features to {out_path} "
        f"(Trainable LST pixels: {trainable_terrestrial_lst.sum():,} / {len(df):,})"
    )

    if manifest_manager is not None:
        manifest_manager.record_entry(
            source="heatsafe_feature_pipeline_v1",
            scene_id=str(metadata.get("scene_id", out_path.stem)),
            acquisition_date=f"{metadata.get('date', '2025-12-18')}T00:00:00Z",
            file_path=out_path,
            metadata={
                "total_rows": len(df),
                "trainable_rows": int(trainable_terrestrial_lst.sum()),
                "water_rows": int(is_water.sum()),
                "season": metadata.get("season", "unknown"),
                "crs": grid_spec["crs"],
            },
        )

    return out_path


def compute_static_terrain(dem_path_or_tiles: Union[Path, List[Path]]) -> Dict[str, np.ndarray]:
    """
    Align the Copernicus DEM to the master grid and derive Horn slope and aspect once.

    Terrain is static, so batch processing computes it a single time and reuses it
    for every Landsat scene.

    Args:
        dem_path_or_tiles (Union[Path, List[Path]]): One DEM raster or a list of tiles to mosaic.

    Returns:
        Dict[str, np.ndarray]: 'elevation', 'slope', 'aspect' (float32) and 'valid_dem' (bool) arrays.
    """
    grid_spec = load_master_grid_spec()
    if isinstance(dem_path_or_tiles, list):
        import rasterio
        from rasterio.merge import merge
        from rasterio.warp import Resampling
        from rasterio.warp import reproject as warp_reproject

        opened_srcs = [rasterio.open(p) for p in dem_path_or_tiles]
        try:
            mosaic_arr, mosaic_trans = merge(opened_srcs)
            aligned_dem = np.full(grid_spec["shape"], np.nan, dtype=np.float32)
            warp_reproject(
                source=mosaic_arr[0],
                destination=aligned_dem,
                src_transform=mosaic_trans,
                src_crs=opened_srcs[0].crs,
                dst_transform=grid_spec["transform"],
                dst_crs=grid_spec["crs"],
                resampling=Resampling.bilinear,
                dst_nodata=np.nan,
            )
        finally:
            for src in opened_srcs:
                src.close()
    else:
        aligned_dem, _ = reproject_to_master_grid(dem_path_or_tiles, resampling_method="bilinear", fill_value=np.nan)

    terrain = compute_horn_terrain_derivatives(dem=aligned_dem, cell_size=grid_spec["cell_size"])
    return {
        "elevation": aligned_dem,
        "slope": terrain["slope"][0],
        "aspect": terrain["aspect"][0],
        "valid_dem": terrain["valid_dem"],
    }


def compute_scene_arrays(
    scene_id: str,
    landsat_bands: Dict[str, Path],
    terrain: Dict[str, np.ndarray],
    acquisition_datetime: str,
) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray], Dict[str, Any]]:
    """
    Turn one Landsat scene into master-grid feature arrays, validity masks, and metadata.

    Reprojects bands, decodes QA bitmasks, scales LST and reflectance, and computes
    spectral indices; terrain comes precomputed from `compute_static_terrain`.

    Args:
        scene_id (str): Landsat scene identifier.
        landsat_bands (Dict[str, Path]): Band alias → local GeoTIFF path.
        terrain (Dict[str, np.ndarray]): Output of `compute_static_terrain`.
        acquisition_datetime (str): ISO 8601 UTC acquisition time.

    Returns:
        Tuple[Dict, Dict, Dict]: (features_dict, masks_dict, metadata) ready for export.
    """
    grid_spec = load_master_grid_spec()

    qa_pixel_raw, _ = reproject_to_master_grid(landsat_bands["QA_PIXEL"], resampling_method="nearest", fill_value=1.0)
    qa_pixel_masks = decode_landsat_qa_pixel(qa_pixel_raw)

    qa_radsat_masks: Dict[str, Any] = {
        "terrain_occlusion_mask": None,
        "band3_sat_mask": None,
        "band4_sat_mask": None,
        "band5_sat_mask": None,
        "band6_sat_mask": None,
    }
    if "QA_RADSAT" in landsat_bands and Path(landsat_bands["QA_RADSAT"]).is_file():
        qa_radsat_raw, _ = reproject_to_master_grid(
            landsat_bands["QA_RADSAT"], resampling_method="nearest", fill_value=0.0
        )
        qa_radsat_masks = decode_landsat_qa_radsat(qa_radsat_raw)

    st_raw, _ = reproject_to_master_grid(landsat_bands["ST_B10"], resampling_method="bilinear", fill_value=0.0)
    scaled_lst, valid_lst = scale_landsat_lst(
        raw_st=st_raw,
        fill_mask=qa_pixel_masks["atmospheric_contamination_mask"],
        terrain_occlusion_mask=qa_radsat_masks.get("terrain_occlusion_mask"),
    )

    reflectance: Dict[str, np.ndarray] = {}
    for alias, sat_key in (("SR_B3", "band3_sat_mask"), ("SR_B4", "band4_sat_mask"),
                           ("SR_B5", "band5_sat_mask"), ("SR_B6", "band6_sat_mask")):
        raw, _ = reproject_to_master_grid(landsat_bands[alias], resampling_method="bilinear", fill_value=0.0)
        reflectance[alias], _ = scale_surface_reflectance(
            raw, fill_mask=qa_pixel_masks["fill_mask"], band_sat_mask=qa_radsat_masks.get(sat_key)
        )

    indices = compute_spectral_indices(
        green=reflectance["SR_B3"], red=reflectance["SR_B4"], nir=reflectance["SR_B5"], swir=reflectance["SR_B6"]
    )

    cols = np.arange(grid_spec["ncols"])
    easting_line = grid_spec["min_easting"] + (cols + 0.5) * grid_spec["cell_size"]
    northing_mid = np.full_like(
        easting_line, grid_spec["min_northing"] + (grid_spec["max_northing"] - grid_spec["min_northing"]) / 2.0
    )
    lon_line, _ = transform("EPSG:32644", "EPSG:4326", easting_line, northing_mid)
    lon_grid = np.tile(lon_line, (grid_spec["nrows"], 1))
    solar_temporal = compute_pixel_mean_local_solar_time(acquisition_datetime, lon_grid)

    features_dict = {
        "elevation": terrain["elevation"],
        "slope": terrain["slope"],
        "aspect": terrain["aspect"],
        "ndvi": indices["ndvi"][0],
        "ndbi": indices["ndbi"][0],
        "mndwi": indices["mndwi"][0],
        "lst_celsius": scaled_lst,
    }
    masks_dict = {
        "valid_dem": terrain["valid_dem"],
        "valid_ndvi": indices["ndvi"][1],
        "valid_ndbi": indices["ndbi"][1],
        "valid_mndwi": indices["mndwi"][1],
        "valid_lst": valid_lst,
        "is_water": qa_pixel_masks["water_mask"],
        "clear_sky": ~qa_pixel_masks["atmospheric_contamination_mask"],
    }
    metadata = {
        "scene_id": scene_id,
        "date": solar_temporal["date"],
        "season": solar_temporal["season"],
        "sin_doy": solar_temporal["sin_doy"],
        "cos_doy": solar_temporal["cos_doy"],
        "utc_decimal": solar_temporal["utc_decimal"],
    }
    return features_dict, masks_dict, metadata


def build_feature_table_from_scene(
    scene_id: str,
    landsat_bands: Dict[str, Path],
    dem_path_or_tiles: Union[Path, List[Path]],
    out_path: Path,
    acquisition_datetime: str = "2025-12-18T05:08:52.167187Z",
    manifest_manager: Optional[DataManifestManager] = None,
) -> Tuple[Path, pd.DataFrame]:
    """
    End-to-end processing pipeline for a single Landsat 8/9 scene:
    reprojects rasters, decodes quality bitmasks, scales radiometry, calculates
    Horn's terrain derivatives and spectral indices, and exports a validated Parquet table.
    """
    terrain = compute_static_terrain(dem_path_or_tiles)
    features_dict, masks_dict, metadata = compute_scene_arrays(
        scene_id=scene_id,
        landsat_bands=landsat_bands,
        terrain=terrain,
        acquisition_datetime=acquisition_datetime,
    )
    exported_path = export_feature_table(
        features_dict=features_dict,
        masks_dict=masks_dict,
        metadata=metadata,
        out_path=out_path,
        manifest_manager=manifest_manager,
    )
    df = pd.read_parquet(exported_path)
    return exported_path, df
