from pathlib import Path
import yaml
from ml.src.commons.logger import get_ml_logger
from ml.src.commons.manifest import DataManifestManager


def test_ml_logger():
    """
    Verify ML logger instantiation, formatting, and message dispatch.
    """
    logger = get_ml_logger("test_module")
    assert logger.name == "test_module"
    logger.info("ML smoke test logger verified")


def test_study_area_config():
    """
    Verify study area configuration contains Nagpur geographic bounds and EPSG specs.
    """
    config_path = Path(__file__).resolve().parent.parent / "configs" / "study_area.yaml"
    assert config_path.is_file(), f"Missing config file at {config_path}"

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["study_area"]["name"] == "Nagpur Urban Area"
    assert data["study_area"]["target_grid_resolution_meters"] == 30
    assert "bounding_box" in data
    assert data["bounding_box"]["min_latitude"] < data["bounding_box"]["max_latitude"]


def test_thresholds_config():
    """
    Verify thresholds configuration contains cloud cover and freshness definitions.
    """
    config_path = Path(__file__).resolve().parent.parent / "configs" / "thresholds.yaml"
    assert config_path.is_file(), f"Missing config file at {config_path}"

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["satellite_ingestion"]["max_cloud_cover_percent"] == 20.0
    assert data["freshness_rules"]["max_scene_age_days"] == 16


def test_data_manifest_manager(tmp_path: Path):
    """
    Verify cryptographic hashing and manifest registration roundtrip.
    """
    test_manifest_file = tmp_path / "data_manifest.json"
    manager = DataManifestManager(manifest_path=test_manifest_file)

    sample_asset = tmp_path / "sample_raster.bin"
    sample_asset.write_bytes(b"GEOSPATIAL_TEST_PIXEL_DATA_12345")

    entry = manager.record_entry(
        source="TestLandsat",
        scene_id="LC08_L2SP_144045_20260315",
        acquisition_date="2026-03-15T05:30:00Z",
        file_path=sample_asset,
        metadata={"cloud_cover": 4.2},
    )

    assert entry["scene_id"] == "LC08_L2SP_144045_20260315"
    assert len(entry["sha256"]) == 64
    assert entry["size_bytes"] == sample_asset.stat().st_size

    loaded = manager.load_all_records()
    assert len(loaded) == 1
    assert loaded[0]["scene_id"] == "LC08_L2SP_144045_20260315"
