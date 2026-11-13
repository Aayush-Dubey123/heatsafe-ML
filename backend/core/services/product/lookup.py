import math
from datetime import date

import numpy as np
from rasterio.transform import Affine, rowcol
from rasterio.warp import transform as warp_transform

# Exposure level cut-offs; must match ml/configs/thresholds.yaml (checked by a test).
EXPOSURE_BREAKS = (25.0, 50.0, 75.0, 90.0)
EXPOSURE_CODES = ("low", "moderate", "high", "very_high", "extreme")
SEASONS = ("summer", "monsoon", "post-monsoon", "winter")
EARTH_RADIUS_KM = 6371.0088


def exposure_level(index: float | None) -> str | None:
    """
    Convert an exposure index (0-100) to its level code.

    Args:
        index (float | None): Exposure index, or None.

    Returns:
        str | None: Level code, or None when there is no value.
    """
    if index is None or not math.isfinite(index):
        return None
    position = sum(1 for cut in EXPOSURE_BREAKS if index >= cut)
    return EXPOSURE_CODES[position]


def scene_age_days(scene_date: str, today: date) -> int:
    """
    Whole days between a scene's acquisition date and today.

    Args:
        scene_date (str): YYYY-MM-DD.
        today (date): Reference date.

    Returns:
        int: Age in days.
    """
    return (today - date.fromisoformat(scene_date)).days


def pixel_for(lat: float, lon: float, transform: Affine, crs: str, shape: tuple[int, int]) -> tuple[int, int] | None:
    """
    Raster row and column containing a WGS84 point.

    Args:
        lat (float): Latitude.
        lon (float): Longitude.
        transform (Affine): Raster transform (projected CRS).
        crs (str): Raster CRS.
        shape (tuple[int, int]): (rows, cols).

    Returns:
        tuple[int, int] | None: (row, col), or None if the point is outside the raster.
    """
    xs, ys = warp_transform("EPSG:4326", crs, [lon], [lat])
    rows, cols = rowcol(transform, xs, ys)
    row_i, col_i = int(rows[0]), int(cols[0])
    if 0 <= row_i < shape[0] and 0 <= col_i < shape[1]:
        return row_i, col_i
    return None


def haversine_km(lat: float, lon: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """
    Great-circle distance from one point to many points.

    Args:
        lat (float): Origin latitude in degrees.
        lon (float): Origin longitude in degrees.
        lats (np.ndarray): Target latitudes.
        lons (np.ndarray): Target longitudes.

    Returns:
        np.ndarray: Distances in kilometres.
    """
    phi1, phi2 = math.radians(lat), np.radians(lats)
    d_phi = phi2 - phi1
    d_lambda = np.radians(lons) - math.radians(lon)
    a = np.sin(d_phi / 2) ** 2 + math.cos(phi1) * np.cos(phi2) * np.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def finite_or_none(value: float, digits: int = 2) -> float | None:
    """
    Round a number for output, mapping NaN and infinity to None.

    Args:
        value (float): Number to convert.
        digits (int): Decimal places.

    Returns:
        float | None: Rounded value or None.
    """
    number = float(value)
    return round(number, digits) if math.isfinite(number) else None
