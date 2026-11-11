"""
HeatSafe-ML map tiles (Phase 9): pre-rendered PNG XYZ tiles in Web Mercator.

Tiles are rendered once by the pipeline so the API can serve static files.
Layout: <out_dir>/<z>/<x>/<y>.png (standard slippy-map scheme, y from the top).
"""

import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject
from rasterio.warp import transform as warp_transform

from ml.src.commons.logger import get_ml_logger
from ml.src.preprocess.align import load_master_grid_spec

logging = get_ml_logger(__name__)

WEB_MERCATOR_HALF = 20037508.342789244


def tile_bounds_mercator(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """
    Web Mercator bounds of an XYZ tile.

    Args:
        z (int): Zoom level.
        x (int): Tile column.
        y (int): Tile row (0 at the top).

    Returns:
        tuple[float, float, float, float]: (left, bottom, right, top) in EPSG:3857 metres.
    """
    size = 2 * WEB_MERCATOR_HALF / (2**z)
    left = -WEB_MERCATOR_HALF + x * size
    top = WEB_MERCATOR_HALF - y * size
    return left, top - size, left + size, top


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    """
    XYZ tile containing a WGS84 point.

    Args:
        lon (float): Longitude in degrees.
        lat (float): Latitude in degrees.
        z (int): Zoom level.

    Returns:
        tuple[int, int]: (x, y) tile indices.
    """
    n = 2**z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def grid_tile_range(z: int) -> tuple[int, int, int, int]:
    """
    Inclusive tile index range covering the master grid at one zoom level.

    Args:
        z (int): Zoom level.

    Returns:
        tuple[int, int, int, int]: (x_min, x_max, y_min, y_max).
    """
    spec = load_master_grid_spec()
    lons, lats = warp_transform(
        spec["crs"], "EPSG:4326",
        [spec["min_easting"], spec["max_easting"], spec["min_easting"], spec["max_easting"]],
        [spec["min_northing"], spec["min_northing"], spec["max_northing"], spec["max_northing"]],
    )
    x0, y1 = lonlat_to_tile(min(lons), min(lats), z)
    x1, y0 = lonlat_to_tile(max(lons), max(lats), z)
    return x0, x1, y0, y1


def colorize(values: np.ndarray, vmin: float, vmax: float, colormap: str) -> np.ndarray:
    """
    Map values to RGBA bytes; NaN becomes fully transparent.

    Args:
        values (np.ndarray): 2D float array.
        vmin (float): Value mapped to the low end of the colour map.
        vmax (float): Value mapped to the high end.
        colormap (str): Matplotlib colour map name.

    Returns:
        np.ndarray: (rows, cols, 4) uint8 RGBA array.
    """
    import matplotlib

    cmap = matplotlib.colormaps[colormap]
    scaled = np.clip((values - vmin) / (vmax - vmin), 0.0, 1.0)
    rgba = (cmap(np.nan_to_num(scaled, nan=0.0)) * 255).astype(np.uint8)
    rgba[..., 3] = np.where(np.isfinite(values), 255, 0)
    return rgba


def render_layer_tiles(array: np.ndarray, out_dir: Path, layer_cfg: dict[str, Any], zoom_min: int, zoom_max: int,
                       tile_size: int = 256) -> dict[str, Any]:
    """
    Render one raster layer to XYZ PNG tiles.

    Each tile is produced by reprojecting the master-grid raster to Web Mercator
    (bilinear); tiles with no data are skipped.

    Args:
        array (np.ndarray): Master-grid raster (NaN = no data).
        out_dir (Path): Layer tile root.
        layer_cfg (dict[str, Any]): colormap, vmin, vmax.
        zoom_min (int): Lowest zoom level.
        zoom_max (int): Highest zoom level.
        tile_size (int): Tile edge in pixels.

    Returns:
        dict[str, Any]: {"tiles": total written, "per_zoom": {z: n}, "expected_per_zoom": {z: n}}.
    """
    spec = load_master_grid_spec()
    source = array.astype(np.float32)
    per_zoom: dict[str, int] = {}
    expected: dict[str, int] = {}
    for z in range(zoom_min, zoom_max + 1):
        x0, x1, y0, y1 = grid_tile_range(z)
        expected[str(z)] = (x1 - x0 + 1) * (y1 - y0 + 1)
        written = 0
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                left, bottom, right, top = tile_bounds_mercator(z, x, y)
                tile = np.full((tile_size, tile_size), np.nan, dtype=np.float32)
                reproject(
                    source=source, destination=tile,
                    src_transform=spec["transform"], src_crs=spec["crs"], src_nodata=np.nan,
                    dst_transform=from_bounds(left, bottom, right, top, tile_size, tile_size),
                    dst_crs="EPSG:3857", dst_nodata=np.nan, resampling=Resampling.bilinear,
                )
                if not np.isfinite(tile).any():
                    continue
                path = out_dir / str(z) / str(x) / f"{y}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                rgba = colorize(tile, float(layer_cfg["vmin"]), float(layer_cfg["vmax"]), str(layer_cfg["colormap"]))
                Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)
                written += 1
        per_zoom[str(z)] = written
    total = sum(per_zoom.values())
    logging.info(f"Rendered {total} tiles into {out_dir}")
    return {"tiles": total, "per_zoom": per_zoom, "expected_per_zoom": expected}
