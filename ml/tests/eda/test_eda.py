import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.src.eda.maps import getis_ord_gi_star, hotspots_to_geojson, seasonal_mean_lst
from ml.src.eda.stats import spearman_by_season
from ml.src.preprocess.align import load_master_grid_spec

SHAPE = tuple(load_master_grid_spec()["shape"])


def test_gi_star_flags_hot_square_and_ignores_nan():
    """
    A warm square in a noisy field becomes a significant hot cluster; NaN cells stay NaN.
    """
    rng = np.random.default_rng(0)
    field = rng.normal(30.0, 1.0, size=(80, 80))
    field[30:50, 30:50] += 8.0
    field[0:5, 0:5] = np.nan

    z = getis_ord_gi_star(field, radius_cells=3, min_neighbours=10)
    assert z[40, 40] > 5.0
    assert z[70, 70] < 1.96
    assert np.isnan(z[0:5, 0:5]).all()


def test_hotspots_geojson_is_wgs84_near_nagpur():
    """
    Polygonised clusters are tagged hot/cold and lie inside the study-area lon/lat box.
    """
    z = np.zeros(SHAPE, dtype=np.float32)
    z[100:120, 100:130] = 4.0
    z[600:610, 700:720] = -3.0
    collection = hotspots_to_geojson(z, 1.96, "summer")
    clusters = sorted(f["properties"]["cluster"] for f in collection["features"])
    assert clusters == ["cold", "hot"]
    lon, lat = np.asarray(collection["features"][0]["geometry"]["coordinates"][0]).T
    assert 78.9 < lon.min() and lon.max() < 79.3 and 21.0 < lat.min() and lat.max() < 21.3


def write_cube(path: Path, lst_value: float, trainable_rows: slice) -> None:
    """
    Write a minimal synthetic scene cube.
    """
    lst = np.full(SHAPE, lst_value, dtype=np.float32)
    trainable = np.zeros(SHAPE, dtype=bool)
    trainable[trainable_rows] = True
    np.savez_compressed(path, lst=lst, trainable=trainable)


def test_seasonal_mean_averages_only_trainable_pixels_of_that_season(tmp_path: Path):
    """
    Seasonal composites average valid observations and ignore other seasons and the test year.
    """
    write_cube(tmp_path / "a.npz", 40.0, slice(0, 10))
    write_cube(tmp_path / "b.npz", 44.0, slice(0, 5))
    write_cube(tmp_path / "c.npz", 20.0, slice(0, 10))
    write_cube(tmp_path / "d.npz", 99.0, slice(0, 10))
    index = pd.DataFrame({
        "scene_id": ["a", "b", "c", "d"],
        "season": ["summer", "summer", "winter", "summer"],
        "usable": [True, True, True, True],
        "split": ["train", "train", "train", "test_year"],
    })
    result = seasonal_mean_lst(index, "summer", tmp_path)
    assert result["scenes"] == ["a", "b"]
    assert result["mean"][0, 0] == 42.0
    assert result["mean"][7, 0] == 40.0
    assert np.isnan(result["mean"][50, 0])
    assert result["count"][0, 0] == 2


def test_spearman_sign_matches_physics_on_synthetic_data():
    """
    More vegetation → cooler surface gives a strongly negative rho.
    """
    rng = np.random.default_rng(1)
    ndvi = rng.uniform(-0.1, 0.8, 5000)
    table = pd.DataFrame({
        "season": "summer",
        "ndvi": ndvi,
        "ndbi": -ndvi + rng.normal(0, 0.05, 5000),
        "mndwi": rng.normal(-0.4, 0.1, 5000),
        "elevation": rng.normal(300, 20, 5000),
        "lst_celsius": 48 - 12 * ndvi + rng.normal(0, 0.5, 5000),
    })
    result = spearman_by_season(table, sample_per_season=3000, seed=0).set_index("driver")
    assert result.loc["ndvi", "rho"] < -0.9
    assert result.loc["ndbi", "rho"] > 0.8
    assert json.loads(result.reset_index().to_json(orient="records"))


def test_fdr_threshold_is_stricter_than_raw_and_handles_noise():
    """
    FDR cut-off is at least 1.96 on clustered data and infinite on pure noise.
    """
    from ml.src.eda.maps import fdr_z_threshold

    rng = np.random.default_rng(3)
    clustered = np.concatenate([rng.normal(0, 1, 10000), rng.normal(6, 1, 2000)])
    assert fdr_z_threshold(clustered, 0.05) >= 1.96
    noise_cut = fdr_z_threshold(rng.normal(0, 1, 2000), 0.05)
    assert noise_cut == float("inf") or noise_cut > 3
