from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

import backend.core.models.product_model  # noqa: F401 - registers tables
from backend.core.database.base_class import Base
from ml.src.pipeline.fallback import RunLock, RunLockError, record_run, serve_last_good
from ml.src.pipeline.run_batch import PipelineSteps, run_once
from ml.src.publish.products import read_latest, set_latest

TODAY = date(2026, 11, 11)
NEW_SCENE = [{"id": "LC08_NEW", "properties": {"datetime": "2026-11-10T05:08:00Z"}}]


def published_root(tmp_path: Path, scene_date: str = "2026-11-03") -> Path:
    """
    Create a published folder holding one earlier good product.
    """
    root = tmp_path / "published"
    set_latest(root, {"version": "good-v1", "scene_id": "LC09_OLD", "scene_date": scene_date, "stale": False})
    return root


def steps(**overrides) -> PipelineSteps:
    """
    Pipeline steps that succeed unless overridden.
    """
    def publish(scene_id: str) -> dict:
        """
        Pretend to publish a bundle.
        """
        return {"version": f"new-{scene_id}", "bundle": "unused", "stale": False, "scene_age_days": 1}

    defaults = {
        "find_new_scenes": lambda since, today: NEW_SCENE,
        "ingest_and_process": lambda scenes: [{"scene_id": "LC08_NEW", "date": "2026-11-10", "usable": True}],
        "publish": publish,
        "load_database": lambda bundle, url: {"products": 1},
        "upload": lambda bundle: {"skipped": True},
    }
    defaults.update(overrides)
    return PipelineSteps(**defaults)


def run(tmp_path: Path, root: Path, **kwargs) -> dict:
    """
    Run the pipeline once with test paths.
    """
    return run_once(today=TODAY, root=root, lock_path=tmp_path / "pipeline.lock", **kwargs)


def raising(error: Exception):
    """
    Build a step that always fails with the given error.
    """
    def step(*args, **kwargs):
        """
        Fail on purpose.
        """
        raise error
    return step


def test_happy_path_publishes_newest_usable_scene(tmp_path: Path):
    """
    With a new clear scene, the run publishes it and releases the lock.
    """
    result = run(tmp_path, published_root(tmp_path), steps=steps())
    assert result["status"] == "published" and result["version"] == "new-LC08_NEW"
    assert not (tmp_path / "pipeline.lock").exists()


def test_failure_injection_network_outage(tmp_path: Path):
    """
    Injected failure 1: the catalogue is unreachable, so the last good product stays, flagged with the cause.
    """
    root = published_root(tmp_path)
    result = run(tmp_path, root, steps=steps(find_new_scenes=raising(RuntimeError("STAC query failed: timeout"))))
    assert result["status"] == "network_error" and result["version"] == "good-v1"
    assert read_latest(root)["last_run_issue"] == "network_error"


def test_failure_injection_corrupt_raster(tmp_path: Path):
    """
    Injected failure 2: a corrupt raster breaks processing, so the last good product stays.
    """
    root = published_root(tmp_path)
    result = run(tmp_path, root, steps=steps(ingest_and_process=raising(OSError("not a valid GeoTIFF"))))
    assert result["status"] == "processing_error" and result["version"] == "good-v1"
    assert read_latest(root)["version"] == "good-v1"


def test_failure_injection_no_new_pass_turns_stale(tmp_path: Path):
    """
    Injected failure 3: no new satellite pass, so the product is kept and marked stale after 16 days.
    """
    root = published_root(tmp_path, scene_date="2026-10-20")
    result = run(tmp_path, root, steps=steps(find_new_scenes=lambda since, today: []))
    assert result["status"] == "no_new_scene" and result["stale"] is True and result["scene_age_days"] == 22
    assert read_latest(root)["stale"] is True


def test_failure_injection_database_down(tmp_path: Path):
    """
    Injected failure 4: the database is down, so the bundle is still published and the outage is reported.
    """
    result = run(tmp_path, published_root(tmp_path), database_url="postgresql+psycopg://x@127.0.0.1:1/none",
                 steps=steps(load_database=raising(ConnectionError("connection refused"))))
    assert result["status"] == "published_db_unavailable" and result["version"] == "new-LC08_NEW"
    assert result["run_recorded"] is False


def test_cloudy_scene_is_not_published(tmp_path: Path):
    """
    A new scene that is too cloudy is skipped and the last good product stays.
    """
    def cloudy(scenes: list) -> list:
        """
        Report the new scene as unusable.
        """
        return [{"scene_id": "LC08_NEW", "date": "2026-11-10", "usable": False}]

    result = run(tmp_path, published_root(tmp_path), steps=steps(ingest_and_process=cloudy))
    assert result["status"] == "no_usable_scene" and result["version"] == "good-v1"


def test_first_run_without_any_product_reports_stale(tmp_path: Path):
    """
    If nothing was ever published and the run fails, the outcome is stale with no version.
    """
    result = run(tmp_path, tmp_path / "empty", steps=steps(find_new_scenes=raising(RuntimeError("down"))))
    assert result["status"] == "network_error" and result["version"] is None and result["stale"] is True


def test_run_lock_blocks_overlap_and_recovers_abandoned_lock(tmp_path: Path):
    """
    A held lock blocks a second run; a lock older than the timeout is replaced.
    """
    lock = tmp_path / "pipeline.lock"
    now = datetime.now(UTC)
    with RunLock(lock, 6, now=now):
        with pytest.raises(RunLockError):
            RunLock(lock, 6, now=now + timedelta(hours=1)).__enter__()
        result = run_once(steps=steps(), today=TODAY, root=published_root(tmp_path), lock_path=lock)
        assert result["status"] == "locked"
    assert not lock.exists()
    lock.write_text('{"started_utc": "2020-01-01T00:00:00+00:00"}')
    with RunLock(lock, 6, now=now):
        assert lock.exists()


def test_runs_are_audited_in_database(tmp_path: Path):
    """
    Each run writes one pipeline_runs row; a missing database never raises.
    """
    url = f"sqlite:///{(tmp_path / 'audit.sqlite3').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    result = run(tmp_path, published_root(tmp_path), database_url=url, steps=steps())
    assert result["run_recorded"] is True
    with engine.connect() as connection:
        rows = connection.execute(text("select status, product_version from pipeline_runs")).all()
    assert rows == [("published", "new-LC08_NEW")]
    engine.dispose()
    assert record_run("sqlite:///nonexistent_dir/x.sqlite3", {"status": "x"}) is False
    assert serve_last_good(tmp_path / "none", "network_error", TODAY, 16)["version"] is None


def test_upload_failure_keeps_product_published_but_is_reported(tmp_path: Path):
    """
    A storage outage after publishing leaves the product online and flags the run as failed.
    """
    result = run(tmp_path, published_root(tmp_path), steps=steps(upload=raising(ConnectionError("storage down"))))
    assert result["status"] == "published_upload_failed" and result["version"] == "new-LC08_NEW"


def test_upload_runs_after_a_successful_publish(tmp_path: Path):
    """
    The upload step receives the new bundle folder exactly once.
    """
    seen: list[Path] = []

    def upload(bundle: Path) -> dict:
        """
        Record the uploaded bundle.
        """
        seen.append(bundle)
        return {}

    result = run(tmp_path, published_root(tmp_path), steps=steps(upload=upload))
    assert result["status"] == "published" and seen == [Path("unused")]
