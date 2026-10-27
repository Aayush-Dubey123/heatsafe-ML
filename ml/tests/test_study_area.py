from pathlib import Path
import json
import yaml
from shapely.geometry import shape
from ml.src.commons.manifest import DataManifestManager


def test_nagpur_boundary_geojson() -> None:
    """
    Verify authoritative Nagpur municipal boundary GeoJSON structure and topology.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If boundary file is missing, invalid JSON, or topologically invalid.
    """
    geojson_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "raw"
        / "boundary"
        / "nagpur_nmc.geojson"
    )
    assert geojson_path.is_file(), f"Boundary file not found at {geojson_path}"

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("type") == "FeatureCollection"
    features = data.get("features", [])
    assert len(features) == 1, f"Expected 1 feature, found {len(features)}"

    feature = features[0]
    geom = shape(feature["geometry"])
    assert geom.is_valid, "Nagpur municipal boundary polygon geometry is invalid"
    assert geom.geom_type in ["Polygon", "MultiPolygon"]

    min_lon, min_lat, max_lon, max_lat = geom.bounds
    assert 78.99 <= min_lon <= 79.05, f"min_lon out of expected bounds: {min_lon}"
    assert 79.15 <= max_lon <= 79.20, f"max_lon out of expected bounds: {max_lon}"
    assert 21.04 <= min_lat <= 21.08, f"min_lat out of expected bounds: {min_lat}"
    assert 21.20 <= max_lat <= 21.25, f"max_lat out of expected bounds: {max_lat}"


def test_nagpur_zones_geojson() -> None:
    """
    Verify the 10 administrative zone boundaries GeoJSON structure and topology.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If zones file is missing or any zone polygon is invalid.
    """
    zones_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "raw"
        / "boundary"
        / "nagpur_zones.geojson"
    )
    assert zones_path.is_file(), f"Zones file not found at {zones_path}"

    with open(zones_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("type") == "FeatureCollection"
    features = data.get("features", [])
    assert len(features) == 10, f"Expected 10 administrative zones, found {len(features)}"

    for feat in features:
        geom = shape(feat["geometry"])
        assert geom.is_valid, f"Zone {feat['properties']['zone_name']} has invalid geometry"
        assert geom.area > 0.0, f"Zone {feat['properties']['zone_name']} has zero area"


def test_study_area_grid_snapping() -> None:
    """
    Verify master 30 m analytical grid configuration and exact coordinate snapping.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If grid parameters fail 30 m snapping, dimensions, or cell count.
    """
    config_path = (
        Path(__file__).resolve().parent.parent / "configs" / "study_area.yaml"
    )
    assert config_path.is_file(), f"Missing config file at {config_path}"

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    assert "projected_grid" in cfg, "Missing 'projected_grid' in study_area.yaml"
    grid = cfg["projected_grid"]

    assert grid["crs"] == "EPSG:32644"
    assert grid["cell_size_meters"] == 30.0
    assert grid["min_easting"] % 30 == 0, "min_easting not snapped to 30 m multiple"
    assert grid["max_easting"] % 30 == 0, "max_easting not snapped to 30 m multiple"
    assert grid["min_northing"] % 30 == 0, "min_northing not snapped to 30 m multiple"
    assert grid["max_northing"] % 30 == 0, "max_northing not snapped to 30 m multiple"

    expected_ncols = int(round((grid["max_easting"] - grid["min_easting"]) / 30.0))
    expected_nrows = int(round((grid["max_northing"] - grid["min_northing"]) / 30.0))

    assert grid["ncols"] == 942
    assert grid["nrows"] == 795
    assert grid["ncols"] == expected_ncols
    assert grid["nrows"] == expected_nrows
    assert grid["total_cells"] == 748890
    assert grid["total_cells"] == grid["ncols"] * grid["nrows"]


def test_manifest_boundary_entry() -> None:
    """
    Verify that boundary assets are registered in data_manifest.json with matching hashes.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If boundary entry is missing or hash verification fails.
    """
    manifest_manager = DataManifestManager()
    records = manifest_manager.load_all_records()

    nmc_record = next(
        (r for r in records if r.get("scene_id") == "nagpur_nmc_boundary_v1"), None
    )
    assert nmc_record is not None, "Missing 'nagpur_nmc_boundary_v1' in data manifest"
    assert nmc_record["size_bytes"] > 0
    assert len(nmc_record["sha256"]) == 64

    boundary_file = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "raw"
        / "boundary"
        / "nagpur_nmc.geojson"
    )
    recalculated_hash = DataManifestManager.compute_sha256(boundary_file)
    assert recalculated_hash == nmc_record["sha256"], "Manifest SHA256 mismatch for boundary"

    zones_record = next(
        (r for r in records if r.get("scene_id") == "nagpur_zones_boundary_v1"), None
    )
    assert zones_record is not None, "Missing 'nagpur_zones_boundary_v1' in data manifest"
    assert zones_record["size_bytes"] > 0
    assert len(zones_record["sha256"]) == 64
