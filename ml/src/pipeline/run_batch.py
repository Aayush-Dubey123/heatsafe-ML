"""
HeatSafe-ML automated inference pipeline (Phase 10).

One run: detect new Landsat scenes → ingest the study-area window → preprocess →
apply Model 1 → publish a versioned bundle → load database tables → audit the run.
Every failure path keeps the last good product online and flags it stale when due.

Usage:
    python -m ml.src.pipeline.run_batch
"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.src.commons.logger import get_ml_logger
from ml.src.dataset.build import INTERIM_DIR, SCENE_INDEX, SCENES_DIR, discover_scenes, save_scene_cube
from ml.src.dataset.splits import load_thresholds
from ml.src.pipeline.fallback import RunLock, RunLockError, record_run, serve_last_good
from ml.src.publish.products import build_bundle, load_bundle_to_database, published_dir, read_latest
from ml.src.publish.storage import StorageNotConfiguredError, get_token, upload_bundle, upload_state

logging = get_ml_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]


def find_new_scenes(since: str | None, today: date) -> list[dict[str, Any]]:
    """
    Ask the STAC catalogue for Landsat 8/9 scenes newer than the last published one.

    Args:
        since (str | None): Date (YYYY-MM-DD) of the last published scene; None uses the lookback window.
        today (date): Reference date.

    Returns:
        list[dict[str, Any]]: STAC features, oldest first.

    Raises:
        RuntimeError: If the catalogue cannot be reached.
    """
    from ml.src.ingest.sources import STACIngestionClient

    lookback = int(load_thresholds()["pipeline"]["lookback_days"])
    start = (date.fromisoformat(since) + timedelta(days=1)) if since else today - timedelta(days=lookback)
    if start > today:
        return []
    scenes = STACIngestionClient().search_landsat_scenes(start_date=start.isoformat(), end_date=today.isoformat())
    return sorted(scenes, key=lambda s: s["properties"]["datetime"])


def ingest_and_process(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Download the study-area window of each new scene, build its cube, and index it.

    Args:
        scenes (list[dict[str, Any]]): STAC features to ingest.

    Returns:
        list[dict[str, Any]]: Index rows (scene_id, date, usable, trainable_fraction) for the processed scenes.

    Raises:
        Exception: Any download or raster error (the caller falls back to the last good product).
    """
    from ml.src.commons.manifest import DataManifestManager
    from ml.src.ingest.__main__ import run_landsat_ingestion
    from ml.src.ingest.sources import STACIngestionClient
    from ml.src.preprocess.align import load_master_grid_spec
    from ml.src.preprocess.features import compute_scene_arrays

    dates = sorted(s["properties"]["datetime"][:10] for s in scenes)
    summary = run_landsat_ingestion(
        STACIngestionClient(), DataManifestManager(), start_date=dates[0], end_date=dates[-1],
        crop_bounds=tuple(load_master_grid_spec()["bounds"]),
    )
    if summary.get("scenes_failed"):
        raise RuntimeError(f"Ingestion failed for {summary['scenes_failed']}")

    wanted = {s["id"] for s in scenes}
    with np.load(INTERIM_DIR / "static_terrain.npz") as terrain_file:
        terrain = {key: terrain_file[key] for key in ("elevation", "slope", "aspect", "valid_dem")}
    min_fraction = float(load_thresholds()["dataset"]["min_scene_trainable_fraction"])
    rows = []
    for scene in discover_scenes():
        if scene["scene_id"] not in wanted:
            continue
        features, masks, metadata = compute_scene_arrays(
            scene["scene_id"], scene["bands"], terrain, scene["acquisition_datetime"]
        )
        trainable = (masks["valid_lst"] & masks["valid_ndvi"] & masks["valid_ndbi"]
                     & masks["valid_mndwi"] & masks["valid_dem"] & ~masks["is_water"])
        save_scene_cube(SCENES_DIR / f"{scene['scene_id']}.npz", features, masks, metadata, trainable)
        fraction = float(trainable.mean())
        lst = np.where(masks["valid_lst"], features["lst_celsius"], np.nan)
        rows.append({
            "scene_id": scene["scene_id"], "date": metadata["date"], "year": int(metadata["date"][:4]),
            "season": metadata["season"], "split": "live", "trainable_fraction": round(fraction, 4),
            "usable": fraction >= min_fraction,
            "city_mean_lst": float(np.nanmean(lst[trainable])) if trainable.any() else np.nan,
        })
    if rows:
        index = pd.read_parquet(SCENE_INDEX)
        index = pd.concat([index[~index["scene_id"].isin([r["scene_id"] for r in rows])], pd.DataFrame(rows)])
        index.sort_values("date").reset_index(drop=True).to_parquet(SCENE_INDEX, index=False)
    return rows


def upload_outputs(bundle: Path) -> dict[str, Any]:
    """
    Upload the new bundle and the refreshed pipeline state to free storage.

    Does nothing when no storage token is configured (e.g. local runs).

    Args:
        bundle (Path): Newly published bundle folder.

    Returns:
        dict[str, Any]: Upload summary, or {"skipped": True} without a token.
    """
    try:
        get_token()
    except StorageNotConfiguredError:
        logging.info("Storage token not set; skipping upload")
        return {"skipped": True}
    return {"bundle": upload_bundle(bundle), "state": upload_state()}


@dataclass
class PipelineSteps:
    """
    The side-effecting steps of a run; replaceable in tests for failure injection.
    """

    find_new_scenes: Callable[[str | None, date], list[dict[str, Any]]] = find_new_scenes
    ingest_and_process: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] = ingest_and_process
    publish: Callable[[str], dict[str, Any]] = field(default=lambda scene_id: build_bundle(scene_id))
    load_database: Callable[[Path, str], dict[str, int]] = load_bundle_to_database
    upload: Callable[[Path], dict[str, Any]] = upload_outputs


def run_once(steps: PipelineSteps | None = None, today: date | None = None, root: Path | None = None,
             database_url: str | None = None, lock_path: Path | None = None) -> dict[str, Any]:
    """
    Execute one pipeline run and return its outcome.

    Status values: published, published_db_unavailable, no_new_scene, no_usable_scene,
    network_error, processing_error, publish_error, locked.

    Args:
        steps (PipelineSteps | None): Step implementations (defaults to the real ones).
        today (date | None): Reference date (defaults to the current UTC date).
        root (Path | None): Published root folder.
        database_url (str | None): Serving database URL; None skips database work.
        lock_path (Path | None): Lock file location.

    Returns:
        dict[str, Any]: status, version, stale, scene_age_days, detail, run_recorded.
    """
    cfg = load_thresholds()
    steps = steps or PipelineSteps()
    today = today or datetime.now(UTC).date()
    root = root or published_dir()
    max_age = int(cfg["freshness_rules"]["max_scene_age_days"])
    lock_path = lock_path or REPO_ROOT / cfg["pipeline"]["lock_file"]
    started = datetime.now(UTC)
    outcome: dict[str, Any] = {"status": "unknown", "version": None, "scene_id": None, "detail": ""}

    def fall_back(status: str, detail: str) -> None:
        """
        Record a non-publishing outcome and keep the last good product online.
        """
        pointer = serve_last_good(root, status, today, max_age)
        outcome.update(status=status, detail=detail[:500], version=pointer.get("version"),
                       stale=pointer.get("stale"), scene_age_days=pointer.get("scene_age_days"))

    try:
        with RunLock(lock_path, float(cfg["pipeline"]["lock_timeout_hours"])):
            previous = read_latest(root)
            try:
                new_scenes = steps.find_new_scenes(previous["scene_date"] if previous else None, today)
            except Exception as error:
                logging.error(f"Error in run_once scene search: {error}")
                fall_back("network_error", f"{type(error).__name__}: {error}")
                new_scenes = None
            if new_scenes is not None and not new_scenes:
                fall_back("no_new_scene", "catalogue has no scene newer than the published one")
            elif new_scenes:
                try:
                    rows = steps.ingest_and_process(new_scenes)
                except Exception as error:
                    logging.error(f"Error in run_once ingest/process: {error}")
                    fall_back("processing_error", f"{type(error).__name__}: {error}")
                    rows = None
                if rows is not None:
                    usable = sorted((r for r in rows if r["usable"]), key=lambda r: r["date"])
                    if not usable:
                        fall_back("no_usable_scene", f"{len(rows)} new scene(s), none clear enough")
                    else:
                        target = usable[-1]
                        outcome["scene_id"] = target["scene_id"]
                        try:
                            published = steps.publish(target["scene_id"])
                        except Exception as error:
                            logging.error(f"Error in run_once publish: {error}")
                            fall_back("publish_error", f"{type(error).__name__}: {error}")
                            published = None
                        if published is not None:
                            outcome.update(status="published", version=published["version"],
                                           stale=published["stale"], scene_age_days=published["scene_age_days"])
                            if database_url:
                                try:
                                    steps.load_database(Path(published["bundle"]), database_url)
                                except Exception as error:
                                    logging.error(f"Error in run_once database load: {error}")
                                    outcome.update(status="published_db_unavailable",
                                                   detail=f"{type(error).__name__}: {error}"[:500])
                            try:
                                steps.upload(Path(published["bundle"]))
                            except Exception as error:
                                logging.error(f"Error in run_once storage upload: {error}")
                                if outcome["status"] == "published":
                                    outcome["status"] = "published_upload_failed"
                                note = f"{outcome.get('detail', '')} upload: {type(error).__name__}"
                                outcome["detail"] = note[:500]
    except RunLockError as error:
        outcome.update(status="locked", detail=str(error))

    outcome["run_recorded"] = record_run(database_url, {
        "started_at": started, "finished_at": datetime.now(UTC), "status": outcome["status"],
        "scene_id": outcome.get("scene_id"), "product_version": outcome.get("version"), "detail": outcome.get("detail"),
    })
    logging.info(f"Pipeline run finished: {outcome}")
    return outcome


if __name__ == "__main__":
    result = run_once(database_url=os.environ.get("HEATSAFE_DATABASE_URL"))
    print(json.dumps(result, indent=2, default=str))
    raise SystemExit(0 if result["status"] in {"published", "no_new_scene", "no_usable_scene"} else 1)
