import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import create_engine, text

import backend.core.models.product_model  # noqa: F401 - registers tables
from backend.core.database.base_class import Base
from ml.src.publish.products import (
    area_metrics,
    freshness,
    load_bundle_to_database,
    read_latest,
    set_latest,
    write_manifest,
)
from ml.src.publish.tiles import colorize, grid_tile_range, lonlat_to_tile, render_layer_tiles, tile_bounds_mercator


def test_tile_math_matches_known_tile():
    """
    The centre of Nagpur falls in the expected zoom-10 tile and tile bounds nest correctly.
    """
    assert lonlat_to_tile(79.0882, 21.1458, 10) == (736, 450)
    left, bottom, right, top = tile_bounds_mercator(1, 1, 0)
    assert left == pytest.approx(0.0) and bottom == pytest.approx(0.0) and right > 2e7 and top > 2e7
    x0, x1, y0, y1 = grid_tile_range(12)
    assert x0 <= x1 and y0 <= y1 and (x1 - x0) <= 4 and (y1 - y0) <= 4


def test_colorize_makes_nan_transparent():
    """
    Finite values are opaque, NaN is transparent, and values are clipped to the range.
    """
    rgba = colorize(np.array([[20.0, np.nan, 999.0]]), 20.0, 60.0, "inferno")
    assert rgba.shape == (1, 3, 4)
    assert rgba[0, 0, 3] == 255 and rgba[0, 1, 3] == 0 and rgba[0, 2, 3] == 255


def test_render_tiles_covers_grid_and_skips_empty(tmp_path: Path):
    """
    A full raster yields every expected tile at a low zoom; an empty raster yields none.
    """
    from ml.src.preprocess.align import load_master_grid_spec

    shape = tuple(load_master_grid_spec()["shape"])
    cfg = {"colormap": "inferno", "vmin": 20.0, "vmax": 60.0}
    summary = render_layer_tiles(np.full(shape, 40.0, dtype=np.float32), tmp_path / "full", cfg, 10, 11)
    assert summary["per_zoom"] == summary["expected_per_zoom"]
    assert (tmp_path / "full" / "10" / "736" / "450.png").is_file()
    empty = render_layer_tiles(np.full(shape, np.nan, dtype=np.float32), tmp_path / "empty", cfg, 10, 10)
    assert empty["tiles"] == 0


def test_freshness_flags_stale_after_16_days():
    """
    Decision D2: a scene older than 16 days is stale.
    """
    assert freshness("2026-11-03", date(2026, 11, 11), 16) == {"scene_age_days": 8, "stale": False}
    assert freshness("2026-11-03", date(2026, 11, 19), 16)["stale"] is False
    assert freshness("2026-11-03", date(2026, 11, 20), 16)["stale"] is True


def test_latest_pointer_is_replaced_atomically(tmp_path: Path):
    """
    The pointer is rewritten in place with no temporary file left behind.
    """
    assert read_latest(tmp_path) is None
    set_latest(tmp_path, {"version": "a"})
    set_latest(tmp_path, {"version": "b"})
    assert read_latest(tmp_path) == {"version": "b"}
    assert [p.name for p in tmp_path.iterdir()] == ["latest.json"]


def test_area_metrics_reports_levels_as_codes():
    """
    Area means are computed per layer and exposure levels come back as codes.
    """
    raster = np.array([[1, 1], [2, 0]])
    lst = {"summer": np.array([[40.0, 42.0], [50.0, 99.0]]), "latest_scene": np.array([[30.0, 30.0], [np.nan, 0.0]])}
    exposure = {"summer": np.array([[10.0, 30.0], [95.0, 0.0]])}
    rows = area_metrics(raster, [1, 2], lst, exposure, [25.0, 50.0, 75.0, 90.0],
                        ["low", "moderate", "high", "very_high", "extreme"])
    by = {(r["locality_id"], r["layer"]): r for r in rows}
    assert by[(1, "summer")]["mean_lst_celsius"] == 41.0 and by[(1, "summer")]["exposure_level"] == "low"
    assert by[(2, "summer")]["exposure_level"] == "extreme"
    assert by[(2, "latest_scene")]["mean_lst_celsius"] is None and by[(1, "latest_scene")]["exposure_index"] is None


def make_bundle(root: Path, version: str) -> Path:
    """
    Write a minimal but complete bundle for database-loading tests.
    """
    bundle = root / version
    (bundle / "vectors").mkdir(parents=True)
    (bundle / "tables").mkdir()
    square = {"type": "Polygon", "coordinates": [[[79.0, 21.1], [79.1, 21.1], [79.1, 21.2], [79.0, 21.1]]]}
    asset = {"properties": {"asset_id": "osm-node-1", "category": "green_space", "name": "Park"},
             "geometry": {"type": "Point", "coordinates": [79.05, 21.15]}}
    (bundle / "vectors" / "zones.geojson").write_text(json.dumps({"features": [
        {"properties": {"zone_id": 1, "zone_name": "Laxmi Nagar"}, "geometry": square}]}))
    (bundle / "vectors" / "localities.geojson").write_text(json.dumps({"features": [
        {"properties": {"locality_id": 1, "locality_name": "Ajni", "area_km2": 4.6, "in_extended_limit": False},
         "geometry": square}]}))
    (bundle / "vectors" / "cooling_assets.geojson").write_text(json.dumps({"features": [asset, asset]}))
    (bundle / "tables" / "zone_metrics.json").write_text(json.dumps([
        {"zone_id": 1, "zone_name": "Laxmi Nagar", "area_km2": 38.7, "season": "summer", "exposure_index": 64.6,
         "risk_rank": 6, "population": 399144, "scene_count": 40}]))
    (bundle / "tables" / "locality_metrics.json").write_text(json.dumps([
        {"locality_id": 1, "layer": "summer", "mean_lst_celsius": 42.9, "exposure_index": 27.3,
         "exposure_level": "moderate"}]))
    write_manifest(bundle, {"version": version, "scene_id": "LC09_TEST", "scene_date": "2026-11-03",
                            "model_version": "m1-test", "created_utc": "2026-11-11T05:00:00+00:00"})
    set_latest(root, {"version": version, "scene_date": "2026-11-03", "stale": False})
    return bundle


def test_bundle_loads_into_database_idempotently(tmp_path: Path):
    """
    Loading the same bundle twice leaves one copy of every row and exactly one latest product.
    """
    url = f"sqlite:///{(tmp_path / 'serve.sqlite3').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    first = make_bundle(tmp_path / "published", "v1")
    counts = load_bundle_to_database(first, url)
    assert counts == load_bundle_to_database(first, url)
    assert counts["cooling_assets"] == 1  # duplicate OSM ids collapse

    second = make_bundle(tmp_path / "published", "v2")
    load_bundle_to_database(second, url)
    with engine.connect() as connection:
        assert connection.execute(text("select count(*) from zones")).scalar() == 1
        assert connection.execute(text("select count(*) from zone_metrics")).scalar() == 2
        latest = connection.execute(text("select version from products where is_latest")).scalars().all()
        assert latest == ["v2"]
        assert connection.execute(text("select count(*) from products")).scalar() == 2
    engine.dispose()


def test_manifest_lists_every_file_with_hash(tmp_path: Path):
    """
    The manifest covers every bundle file and hashes re-verify.
    """
    from ml.src.models.core.evaluate import sha256_file

    bundle = make_bundle(tmp_path, "v1")
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["file_count"] == 5
    assert all(sha256_file(bundle / f["path"]) == f["sha256"] for f in manifest["files"])
