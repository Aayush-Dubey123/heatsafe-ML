"""
HeatSafe-ML Spatial Alignment, Reprojection & Radiometric Preprocessing Engine.
Enforces Master 30 m Grid (EPSG:32644) alignment, explicit QA bitmask decoding,
and decoupled radiometric quality validation for Landsat 8/9 and auxiliary sensors.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject
import yaml

from ml.src.commons.logger import get_ml_logger

logger = get_ml_logger(__name__)


def load_master_grid_spec(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load and validate the master 30 m grid specification from study_area.yaml.

    Returns:
        Dict containing grid properties:
            - 'crs': Target CRS string ("EPSG:32644")
            - 'cell_size': Cell dimension in meters (30.0)
            - 'min_easting': Origin easting (285960.0)
            - 'max_easting': Maximum easting (314220.0)
            - 'min_northing': Origin northing (2328030.0)
            - 'max_northing': Maximum northing (2351880.0)
            - 'ncols': Number of columns (942)
            - 'nrows': Number of rows (795)
            - 'total_cells': Total raster cells (748890)
            - 'transform': Affine transform object for rasterio
            - 'bounds': Tuple of (min_easting, min_northing, max_easting, max_northing)
    """
    if config_path is None:
        config_path = (
            Path(__file__).resolve().parent.parent.parent
            / "configs"
            / "study_area.yaml"
        )

    if not config_path.is_file():
        raise FileNotFoundError(f"Study area configuration not found at: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if "projected_grid" not in cfg:
        raise KeyError(
            f"Missing 'projected_grid' section in configuration: {config_path}"
        )

    grid = cfg["projected_grid"]
    crs = grid.get("crs", "EPSG:32644")
    cell_size = float(grid.get("cell_size_meters", 30.0))
    min_easting = float(grid.get("min_easting", 285960.0))
    max_easting = float(grid.get("max_easting", 314220.0))
    min_northing = float(grid.get("min_northing", 2328030.0))
    max_northing = float(grid.get("max_northing", 2351880.0))
    ncols = int(grid.get("ncols", 942))
    nrows = int(grid.get("nrows", 795))
    total_cells = int(grid.get("total_cells", 748890))

    # Verify geometry consistency
    expected_width = ncols * cell_size
    actual_width = max_easting - min_easting
    expected_height = nrows * cell_size
    actual_height = max_northing - min_northing

    if not np.isclose(expected_width, actual_width, atol=1e-3):
        raise ValueError(
            f"Grid width mismatch: ncols * cell_size ({expected_width}) != max_e - min_e ({actual_width})"
        )
    if not np.isclose(expected_height, actual_height, atol=1e-3):
        raise ValueError(
            f"Grid height mismatch: nrows * cell_size ({expected_height}) != max_n - min_n ({actual_height})"
        )

    # Master Affine Transform: (cell_size, 0, min_easting, 0, -cell_size, max_northing)
    master_transform = Affine(
        cell_size, 0.0, min_easting, 0.0, -cell_size, max_northing
    )

    return {
        "crs": crs,
        "cell_size": cell_size,
        "min_easting": min_easting,
        "max_easting": max_easting,
        "min_northing": min_northing,
        "max_northing": max_northing,
        "ncols": ncols,
        "nrows": nrows,
        "total_cells": total_cells,
        "shape": (nrows, ncols),
        "transform": master_transform,
        "bounds": (min_easting, min_northing, max_easting, max_northing),
    }


def reproject_to_master_grid(
    src_path: Path,
    resampling_method: str = "bilinear",
    fill_value: float = np.nan,
    config_path: Optional[Path] = None,
    dst_dtype: Optional[np.dtype] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Reproject and resample an input raster strictly onto the master 30 m grid (EPSG:32644).

    Args:
        src_path: Path to source GeoTIFF/raster file.
        resampling_method: 'bilinear' (continuous surface/DEM) or 'nearest' (QA/discrete masks).
        fill_value: Value to populate out-of-bounds or NoData cells (default: np.nan).
        config_path: Optional path to study area YAML config.
        dst_dtype: Optional destination numpy dtype. Inferred from fill_value and source if None.

    Returns:
        Tuple of (destination_array of shape (795, 942), metadata_dict).
    """
    if not Path(src_path).is_file():
        raise FileNotFoundError(f"Source raster file not found: {src_path}")

    grid_spec = load_master_grid_spec(config_path)
    nrows, ncols = grid_spec["shape"]

    method_map = {
        "bilinear": Resampling.bilinear,
        "nearest": Resampling.nearest,
        "cubic": Resampling.cubic,
        "average": Resampling.average,
    }
    if resampling_method.lower() not in method_map:
        raise ValueError(
            f"Unsupported resampling method '{resampling_method}'. Choose from: {list(method_map.keys())}"
        )
    resampling_enum = method_map[resampling_method.lower()]

    with rasterio.open(src_path) as src:
        # Determine output dtype
        if dst_dtype is None:
            if np.isnan(fill_value):
                dst_dtype = np.float32
            else:
                # Retain integer source type if fill_value is integer-compatible
                src_type = np.dtype(src.dtypes[0])
                if np.issubdtype(src_type, np.integer) and float(int(fill_value)) == float(fill_value):
                    dst_dtype = src_type
                else:
                    dst_dtype = np.float32

        dst_array = np.full((nrows, ncols), fill_value, dtype=dst_dtype)

        reproject(
            source=rasterio.band(src, 1),
            destination=dst_array,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=grid_spec["transform"],
            dst_crs=grid_spec["crs"],
            resampling=resampling_enum,
            dst_nodata=fill_value,
        )

        meta = {
            "source_path": str(src_path),
            "source_crs": str(src.crs),
            "source_shape": src.shape,
            "target_crs": grid_spec["crs"],
            "target_shape": (nrows, ncols),
            "transform": grid_spec["transform"],
            "resampling": resampling_method,
            "dtype": str(dst_dtype),
        }

    return dst_array, meta


def decode_landsat_qa_pixel(raw_qa: np.ndarray) -> Dict[str, np.ndarray]:
    """
    Decode USGS Landsat 8-9 Collection 2 QA_PIXEL bitmasks into explicit, decoupled quality masks.

    Bit Definitions (USGS Landsat Collection 2 Level 2 QA_PIXEL):
        Bit 0: Fill (0 = Image data, 1 = Fill / NoData)
        Bit 1: Dilated Cloud
        Bit 2: Cirrus
        Bit 3: Cloud
        Bit 4: Cloud Shadow
        Bit 5: Snow / Ice
        Bit 6: Clear (1 = Clear sky, 0 = Obscured)
        Bit 7: Water (1 = Water, 0 = Land)

    Decoupling Principle:
        Atmospheric / cloud / snow contamination is decoupled from water masking.
        Water pixels are not destroyed or masked blindly; they are preserved with explicit
        'is_water' flags, allowing aquatic vs terrestrial analysis to be configured downstream.

    Returns:
        Dict[str, np.ndarray] of boolean masks:
            - 'fill_mask'
            - 'dilated_cloud_mask'
            - 'cirrus_mask'
            - 'cloud_mask'
            - 'cloud_shadow_mask'
            - 'snow_mask'
            - 'clear_mask'
            - 'water_mask'
            - 'atmospheric_contamination_mask' (fill | dilated_cloud | cirrus | cloud | cloud_shadow | snow)
    """
    qa_int = raw_qa.astype(np.uint16)

    fill_mask = (qa_int & (1 << 0)) != 0
    dilated_cloud_mask = (qa_int & (1 << 1)) != 0
    cirrus_mask = (qa_int & (1 << 2)) != 0
    cloud_mask = (qa_int & (1 << 3)) != 0
    cloud_shadow_mask = (qa_int & (1 << 4)) != 0
    snow_mask = (qa_int & (1 << 5)) != 0
    clear_mask = (qa_int & (1 << 6)) != 0
    water_mask = (qa_int & (1 << 7)) != 0

    # Atmospheric and sensor contamination mask (explicitly includes snow/ice; water is kept separate)
    atmospheric_contamination_mask = (
        fill_mask
        | dilated_cloud_mask
        | cirrus_mask
        | cloud_mask
        | cloud_shadow_mask
        | snow_mask
    )

    return {
        "fill_mask": fill_mask,
        "dilated_cloud_mask": dilated_cloud_mask,
        "cirrus_mask": cirrus_mask,
        "cloud_mask": cloud_mask,
        "cloud_shadow_mask": cloud_shadow_mask,
        "snow_mask": snow_mask,
        "clear_mask": clear_mask,
        "water_mask": water_mask,
        "atmospheric_contamination_mask": atmospheric_contamination_mask,
    }


def decode_landsat_qa_radsat(raw_radsat: np.ndarray) -> Dict[str, np.ndarray]:
    """
    Decode USGS Landsat 8-9 Collection 2 QA_RADSAT bitmask for radiometric saturation and occlusion.

    Bit Definitions (USGS Landsat Collection 2 Level 2 Table 6-4 / Table 3-4):
        Bit 0: Band 1 Saturation
        Bit 1: Band 2 Saturation
        Bit 2: Band 3 Saturation (Green)
        Bit 3: Band 4 Saturation (Red)
        Bit 4: Band 5 Saturation (NIR)
        Bit 5: Band 6 Saturation (SWIR-1)
        Bit 6: Band 7 Saturation (SWIR-2)
        Bit 8: Band 9 Saturation
        Bit 11: Terrain Occlusion

    Decoupling Principle:
        QA_RADSAT saturation bits apply to OLI reflective optical bands (B1-B7, B9) and
        terrain occlusion (Bit 11). Thermal validation does NOT rely on QA_RADSAT optical bits,
        evaluating sensor quality through designated fill checks (raw_st <= 0), terrain occlusion,
        and physical radiometric screening.

    Returns:
        Dict[str, np.ndarray] of boolean masks:
            - 'band1_sat_mask'
            - 'band2_sat_mask'
            - 'band3_sat_mask'
            - 'band4_sat_mask'
            - 'band5_sat_mask'
            - 'band6_sat_mask'
            - 'band7_sat_mask'
            - 'band9_sat_mask'
            - 'terrain_occlusion_mask'
            - 'any_optical_sat_mask'
    """
    radsat_int = raw_radsat.astype(np.uint16)

    band1_sat = (radsat_int & (1 << 0)) != 0
    band2_sat = (radsat_int & (1 << 1)) != 0
    band3_sat = (radsat_int & (1 << 2)) != 0
    band4_sat = (radsat_int & (1 << 3)) != 0
    band5_sat = (radsat_int & (1 << 4)) != 0
    band6_sat = (radsat_int & (1 << 5)) != 0
    band7_sat = (radsat_int & (1 << 6)) != 0
    band9_sat = (radsat_int & (1 << 8)) != 0
    terrain_occlusion = (radsat_int & (1 << 11)) != 0

    any_optical_sat = (
        band1_sat
        | band2_sat
        | band3_sat
        | band4_sat
        | band5_sat
        | band6_sat
        | band7_sat
        | band9_sat
    )

    return {
        "band1_sat_mask": band1_sat,
        "band2_sat_mask": band2_sat,
        "band3_sat_mask": band3_sat,
        "band4_sat_mask": band4_sat,
        "band5_sat_mask": band5_sat,
        "band6_sat_mask": band6_sat,
        "band7_sat_mask": band7_sat,
        "band9_sat_mask": band9_sat,
        "terrain_occlusion_mask": terrain_occlusion,
        "any_optical_sat_mask": any_optical_sat,
    }


def scale_landsat_lst(
    raw_st: np.ndarray,
    fill_mask: np.ndarray,
    terrain_occlusion_mask: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Scale Landsat Collection 2 Level 2 Surface Temperature (ST_B10) to degrees Celsius.

    Mask Invalid Values Before Scaling:
        Pixels where raw_st <= 0 (USGS designated fill/NoData is 0) or fill_mask is True
        or terrain_occlusion_mask is True are invalid and set to np.nan.

    Radiometric Conversion Formula:
        LST_Kelvin = DN_raw * 0.00341802 + 149.0
        LST_Celsius = LST_Kelvin - 273.15

    Args:
        raw_st: Raw digital number array of Landsat Band 10 Surface Temperature.
        fill_mask: Boolean mask indicating fill pixels (True = fill/invalid).
        terrain_occlusion_mask: Optional boolean mask of terrain occlusion from QA_RADSAT.

    Returns:
        Tuple of (scaled_lst_celsius [float32 array with NaNs for invalid pixels], valid_lst_mask [bool array]).
    """
    # Raw values <= 0 or fill indicate uncalibrated / NoData
    invalid_mask = (raw_st <= 0) | fill_mask | np.isnan(raw_st)
    if terrain_occlusion_mask is not None:
        invalid_mask = invalid_mask | terrain_occlusion_mask

    valid_mask = ~invalid_mask

    scaled_lst = np.full(raw_st.shape, np.nan, dtype=np.float32)
    if np.any(valid_mask):
        raw_valid = raw_st[valid_mask].astype(np.float64)
        kelvin = raw_valid * 0.00341802 + 149.0
        celsius = kelvin - 273.15
        scaled_lst[valid_mask] = celsius.astype(np.float32)

    return scaled_lst, valid_mask


def scale_surface_reflectance(
    raw_sr: np.ndarray,
    fill_mask: np.ndarray,
    band_sat_mask: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Scale Landsat Collection 2 Level 2 Surface Reflectance (SR_B*) bands without destructive clipping.

    Scaling Formula:
        SR = DN_raw * 0.0000275 - 0.2

    Preservation Principle:
        Values are NOT clamped or clipped to [0.0, 1.0]. Raw physical values are preserved.
        An independent boolean validity mask is returned where:
            validity_flag = (SR >= 0.0) & (SR <= 1.0) & ~band_sat_mask & ~fill_mask

    Args:
        raw_sr: Raw digital number array of Landsat Surface Reflectance band.
        fill_mask: Boolean mask indicating fill pixels (True = fill/invalid).
        band_sat_mask: Optional boolean mask indicating radiometric saturation for this specific band.

    Returns:
        Tuple of (scaled_sr [float32 array with NaNs for fill], validity_mask [bool array]).
    """
    invalid_fill = (raw_sr <= 0) | fill_mask | np.isnan(raw_sr)
    valid_raw = ~invalid_fill

    scaled_sr = np.full(raw_sr.shape, np.nan, dtype=np.float32)
    if np.any(valid_raw):
        raw_valid = raw_sr[valid_raw].astype(np.float64)
        scaled_sr[valid_raw] = (raw_valid * 0.0000275 - 0.2).astype(np.float32)

    # Compute independent validity flag
    validity_flag = valid_raw & (scaled_sr >= 0.0) & (scaled_sr <= 1.0)
    if band_sat_mask is not None:
        validity_flag = validity_flag & (~band_sat_mask)

    return scaled_sr, validity_flag
