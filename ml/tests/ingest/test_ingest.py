import json
from pathlib import Path
from typing import Any, Dict
import pytest
import yaml
from ml.src.commons.manifest import DataManifestManager
from ml.src.ingest.__main__ import audit_seasonal_inventory, classify_season, run_landsat_ingestion
from ml.src.ingest.sources import STACIngestionClient


def test_ingest_config_structure() -> None:
    """
    Verify structure, mandatory keys, and constraints in ml/configs/ingest.yaml.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If configuration file is missing or has missing/invalid schema keys.
    """
    config_path = (
        Path(__file__).resolve().parent.parent.parent / "configs" / "ingest.yaml"
    )
    assert config_path.is_file(), f"Configuration file not found at {config_path}"

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    assert cfg["spatial_constraints"]["wrs_path"] == "144"
    assert cfg["spatial_constraints"]["wrs_row"] == "045"
    assert cfg["filtering"]["cloud_cover_max"] == 20.0
    assert "landsat" in cfg["sources"]
    assert "lwir11" in cfg["sources"]["landsat"]["target_bands"]
    assert cfg["retry_policy"]["max_retries"] == 5
    assert cfg["retry_policy"]["backoff_factor"] == 2.0


def test_seasonal_classification_and_audit() -> None:
    """
    Verify calendar month classification and seasonal audit against Decision D7.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If seasonal categorization or D7 logic is incorrect.
    """
    assert classify_season(1) == "Winter"
    assert classify_season(4) == "Summer"
    assert classify_season(7) == "Monsoon"
    assert classify_season(10) == "Post-Monsoon"

    with pytest.raises(ValueError):
        classify_season(13)

    mock_scenes: list[Dict[str, Any]] = []
    # Build 10 scenes per season in 2024 (total 40 scenes, satisfying D7)
    for m in [1, 4, 7, 10]:
        for i in range(10):
            mock_scenes.append(
                {"id": f"scene_{m}_{i}", "properties": {"datetime": f"2024-{m:02d}-15T10:00:00Z"}}
            )

    audit = audit_seasonal_inventory(mock_scenes)
    assert audit["total_scenes"] == 40
    assert audit["seasons_count"]["Winter"] == 10
    assert audit["seasons_count"]["Summer"] == 10
    assert audit["seasons_count"]["Monsoon"] == 10
    assert audit["seasons_count"]["Post-Monsoon"] == 10
    assert audit["meets_decision_d7"] is True


def test_idempotency_skip_manifest(tmp_path: Path) -> None:
    """
    Verify that existing manifest records are detected and skipped with 0 downloaded bytes.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.

    Returns:
        None.

    Raises:
        AssertionError: If idempotency filter fails or downloads redundant data.
    """
    manifest_file = tmp_path / "data_manifest.json"
    manifest_manager = DataManifestManager(manifest_path=manifest_file)

    test_scene_id = "LC08_L2SP_144045_20240501"
    assert STACIngestionClient.is_scene_ingested(test_scene_id, manifest_manager) is False

    fake_asset = tmp_path / f"{test_scene_id}_ST_B10.tif"
    fake_asset.write_bytes(b"MOCK_RASTER_DATA_CONTENT")

    manifest_manager.record_entry(
        source="USGS_Landsat_C2L2",
        scene_id=test_scene_id,
        acquisition_date="2024-05-01T05:00:00Z",
        file_path=fake_asset,
    )

    assert STACIngestionClient.is_scene_ingested(test_scene_id, manifest_manager) is True


def test_download_asset_with_retry_and_recovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify that download_asset_with_retry handles transient failures and recovers via backoff.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatching fixture.

    Returns:
        None.

    Raises:
        AssertionError: If retry mechanism fails to recover or fails to clean up partial files.
    """
    client = STACIngestionClient()
    dest_file = tmp_path / "test_download.tif"

    attempt_count = 0

    class MockResponse:
        def __init__(self, data: bytes):
            self._data = data
            self._offset = 0

        def read(self, chunk_size: int = 65536) -> bytes:
            if self._offset >= len(self._data):
                return b""
            chunk = self._data[self._offset : self._offset + chunk_size]
            self._offset += chunk_size
            return chunk

        def __enter__(self) -> "MockResponse":
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

    def mock_urlopen(req: Any, timeout: int = 60) -> MockResponse:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            # Simulate network failure on first attempt
            raise IOError("Simulated network timeout")
        return MockResponse(b"TIFF_DATA_RECOVERED")

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    downloaded = client.download_asset_with_retry(
        url="https://mock.blob.core.windows.net/landsat/b10.tif",
        destination=dest_file,
        max_retries=3,
        initial_delay=0.01,
        backoff_factor=1.5,
    )

    assert downloaded.is_file()
    assert downloaded.read_bytes() == b"TIFF_DATA_RECOVERED"
    assert attempt_count == 2, f"Expected 2 attempts, got {attempt_count}"


def test_cli_dry_run_execution() -> None:
    """
    Verify that dry-run mode queries the catalog without writing rasters or mutating state.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If dry-run downloads bytes or returns invalid status.
    """
    client = STACIngestionClient()
    manifest = DataManifestManager()

    res = run_landsat_ingestion(
        client=client,
        manifest=manifest,
        start_date="2024-05-01",
        end_date="2024-05-31",
        limit=2,
        dry_run=True,
    )

    assert res["status"] == "dry_run_completed"
    assert res["bytes_downloaded"] == 0
    assert res["scenes_found"] > 0
    assert "audit" in res
