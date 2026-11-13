import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_bounds, transform_geom

from backend.core import logger

logging = logger(__name__)

SEASONS = ("summer", "monsoon", "post-monsoon", "winter")


class ProductStore:
    """
    One published product bundle held in memory.

    Rasters are small (about 3 MB per layer for the 795 x 942 grid), so every lookup
    is an array read; the API never runs the model (Decision T10).

    Attributes:
        version (str): Bundle version.
        pointer (dict[str, Any]): Contents of latest.json.
        manifest (dict[str, Any]): Bundle manifest.
        bundle_dir (Path): Folder holding the bundle files (tiles are served from disk).
    """

    def __init__(self, bundle_dir: Path, pointer: dict[str, Any]) -> None:
        """
        Load every array and table of a bundle.

        Args:
            bundle_dir (Path): Bundle folder.
            pointer (dict[str, Any]): latest.json contents.

        Raises:
            FileNotFoundError: If a required bundle file is missing.
        """
        self.bundle_dir = bundle_dir
        self.pointer = pointer
        self.version = str(pointer["version"])
        self.manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))

        self.rasters: dict[str, np.ndarray] = {}
        names = ["latest_lst", "latest_lst_p05", "latest_lst_p95", "latest_observed_mask"]
        names += [f"lst_{s}" for s in SEASONS] + [f"exposure_{s}" for s in SEASONS]
        for name in names:
            with rasterio.open(bundle_dir / "cogs" / f"{name}.tif") as source:
                self.rasters[name] = source.read(1).astype(np.float32)
                if name == "latest_lst":
                    self.transform, self.crs, self.shape = source.transform, str(source.crs), source.shape
                    self.bounds = transform_bounds(source.crs, "EPSG:4326", *source.bounds)

        self.zone_features = self._read_geojson("zones")["features"]
        self.locality_features = self._read_geojson("localities")["features"]
        self.zone_grid = self._burn(self.zone_features, "zone_id")
        self.locality_grid = self._burn(self.locality_features, "locality_id")
        self.zones = {int(f["properties"]["zone_id"]): f["properties"] for f in self.zone_features}
        self.localities = {int(f["properties"]["locality_id"]): f["properties"] for f in self.locality_features}

        self.zone_metrics: list[dict[str, Any]] = self._read_json("tables/zone_metrics.json")
        self.locality_metrics: list[dict[str, Any]] = self._read_json("tables/locality_metrics.json")
        self.hotspots = {s: self._read_json(f"vectors/hotspots_{s}.geojson") for s in SEASONS
                         if (bundle_dir / "vectors" / f"hotspots_{s}.geojson").is_file()}

        assets = self._read_geojson("cooling_assets")["features"]
        self.asset_ids = [a["properties"]["asset_id"] for a in assets]
        self.asset_categories = np.array([a["properties"]["category"] for a in assets])
        self.asset_names = [a["properties"].get("name") for a in assets]
        self.asset_lons = np.array([a["geometry"]["coordinates"][0] for a in assets], dtype=np.float64)
        self.asset_lats = np.array([a["geometry"]["coordinates"][1] for a in assets], dtype=np.float64)
        logging.info(f"Loaded product {self.version}: {len(assets)} assets, grid {self.shape}")

    def _read_json(self, relative: str) -> Any:
        """
        Parse a JSON file inside the bundle.

        Args:
            relative (str): Path relative to the bundle folder.

        Returns:
            Any: Parsed content.
        """
        return json.loads((self.bundle_dir / relative).read_text(encoding="utf-8"))

    def _read_geojson(self, name: str) -> dict[str, Any]:
        """
        Parse a GeoJSON file from the bundle's vectors folder.

        Args:
            name (str): File stem, e.g. "zones".

        Returns:
            dict[str, Any]: FeatureCollection.
        """
        return self._read_json(f"vectors/{name}.geojson")

    def _burn(self, features: list[dict[str, Any]], id_key: str) -> np.ndarray:
        """
        Rasterise polygons onto the product grid so a point maps to an area id in O(1).

        Args:
            features (list[dict[str, Any]]): GeoJSON features (WGS84).
            id_key (str): Property holding the integer id.

        Returns:
            np.ndarray: int16 grid (0 = outside every polygon).
        """
        shapes = [(transform_geom("EPSG:4326", self.crs, f["geometry"]), int(f["properties"][id_key]))
                  for f in features]
        return rasterize(shapes, out_shape=self.shape, transform=self.transform, fill=0, dtype="int16")

    def tile_path(self, layer: str, z: int, x: int, y: int) -> Path | None:
        """
        Path of a pre-rendered tile, or None if it does not exist.

        Args:
            layer (str): Whitelisted tile layer id.
            z (int): Zoom.
            x (int): Tile column.
            y (int): Tile row.

        Returns:
            Path | None: PNG path if present.
        """
        path = self.bundle_dir / "tiles" / layer / str(z) / str(x) / f"{y}.png"
        return path if path.is_file() else None


def load_store(root: Path) -> ProductStore | None:
    """
    Load the product that `latest.json` points at.

    Args:
        root (Path): Folder holding bundles and latest.json.

    Returns:
        ProductStore | None: The store, or None if nothing usable is published (the API then answers 503).
    """
    pointer_file = root / "latest.json"
    if not pointer_file.is_file():
        logging.warning(f"No latest.json in {root}; API will report no product available")
        return None
    try:
        pointer = json.loads(pointer_file.read_text(encoding="utf-8"))
        return ProductStore(root / str(pointer["version"]), pointer)
    except Exception as error:
        logging.error(f"Error in load_store: {type(error).__name__}: {error}")
        return None
