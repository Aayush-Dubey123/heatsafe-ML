import numpy as np
import pandas as pd
import pytest

from ml.src.exposure.index import (
    bootstrap_zone_exposure,
    composite_mean,
    exposure_levels,
    percentile_rank,
    rasterize_zones,
    zone_means,
)
from ml.src.exposure.vulnerability import (
    assert_no_individual_fields,
    assets_per_zone,
    minmax,
    rank_with_intervals,
    vulnerability_score,
)


def test_percentile_rank_bounds_ties_and_nan():
    """
    Ranks run 0-100, ties share a mid-rank, and NaN stays NaN.
    """
    values = np.array([1.0, 2.0, 2.0, 3.0, np.nan])
    rank = percentile_rank(values, values)
    assert rank[0] < rank[1] == rank[2] < rank[3]
    assert 0 < rank[0] and rank[3] < 100
    assert np.isnan(rank[4])
    with pytest.raises(ValueError):
        percentile_rank(values, np.array([np.nan]))


def test_exposure_levels_use_codes_not_text():
    """
    Index values map to language-neutral codes; NaN maps to no_data.
    """
    codes = ["low", "moderate", "high", "very_high", "extreme"]
    levels = exposure_levels(np.array([10.0, 25.0, 60.0, 80.0, 95.0, np.nan]), [25.0, 50.0, 75.0, 90.0], codes)
    assert levels.tolist() == ["low", "moderate", "high", "very_high", "extreme", "no_data"]
    with pytest.raises(ValueError):
        exposure_levels(np.array([1.0]), [50.0], codes)


def test_composite_mean_ignores_nan_and_honours_weights():
    """
    Composites skip missing observations and count scenes by bootstrap weight.
    """
    stack = np.array([[10.0, np.nan], [20.0, 30.0]], dtype=np.float32)
    assert composite_mean(stack).tolist() == [15.0, 30.0]
    assert composite_mean(stack, np.array([3, 1])).tolist() == [12.5, 30.0]


def test_bootstrap_keeps_clear_hot_zone_on_top():
    """
    A zone that is hotter in every scene stays ranked first across all replicates.
    """
    rng = np.random.default_rng(0)
    zone_of_pixel = np.repeat([1, 2, 3], 200)
    base = np.repeat([45.0, 40.0, 35.0], 200)
    stack = (base[None, :] + rng.normal(0, 1.0, size=(12, 600))).astype(np.float32)
    stack[0, :50] = np.nan
    replicates = bootstrap_zone_exposure(stack, zone_of_pixel, [1, 2, 3], n_resamples=100, seed=1)
    assert replicates.shape == (100, 3)
    assert (replicates[:, 0] > replicates[:, 1]).all() and (replicates[:, 1] > replicates[:, 2]).all()

    ranks = rank_with_intervals(replicates.mean(axis=0), replicates)
    assert ranks["rank"].tolist() == [1, 2, 3]
    assert ranks["rank_low"].tolist() == ranks["rank_high"].tolist() == [1, 2, 3]


def test_rank_intervals_widen_when_zones_are_indistinguishable():
    """
    Zones with overlapping scores get rank intervals wider than a single rank.
    """
    rng = np.random.default_rng(2)
    replicates = rng.normal(50.0, 5.0, size=(500, 4))
    ranks = rank_with_intervals(np.array([50.1, 50.0, 49.9, 49.8]), replicates)
    assert (ranks["rank_high"] - ranks["rank_low"] >= 2).all()


def test_vulnerability_score_scaling_and_weights():
    """
    The most vulnerable zone on every component scores 100, the least 0.
    """
    table = pd.DataFrame({
        "population_density_per_km2": [1000.0, 5000.0, 9000.0],
        "share_age_60_plus": [0.08, 0.10, 0.12],
        "green_deficit": [0.2, 0.5, 0.8],
    })
    score = vulnerability_score(table, {"population_density_per_km2": 1, "share_age_60_plus": 1, "green_deficit": 1})
    assert score.tolist() == [0.0, 50.0, 100.0]
    assert minmax(pd.Series([3.0, 3.0])).tolist() == [0.5, 0.5]


def test_real_zones_rasterize_to_ten_disjoint_zones():
    """
    The 10 NMC zones cover ~211 km2 on the grid with ids 1-10 and no gaps in numbering.
    """
    raster, table = rasterize_zones()
    assert sorted(table["zone_id"]) == list(range(1, 11))
    assert set(np.unique(raster)) == set(range(0, 11))
    assert table["area_km2"].sum() == pytest.approx(210.8, abs=1.5)
    assert zone_means(np.ones(raster.size), raster.ravel(), [1, 2]).tolist() == [1.0, 1.0]


def test_assets_are_counted_in_their_zone_only():
    """
    A point inside Nagpur is counted once in one zone; a point far away is ignored.
    """
    raster, table = rasterize_zones()
    assets = {"features": [
        {"geometry": {"coordinates": [79.0882, 21.1458]}, "properties": {"category": "green_space"}},
        {"geometry": {"coordinates": [77.0, 28.6]}, "properties": {"category": "green_space"}},
    ]}
    counts = assets_per_zone(assets, raster, [int(z) for z in table["zone_id"]])
    assert int(counts["assets_green_space"].sum()) == 1


def test_schema_guard_blocks_individual_level_fields():
    """
    Zone-level columns pass; person- or household-level columns are rejected.
    """
    assert_no_individual_fields(["zone_id", "zone_name", "population", "share_age_60_plus", "risk_rank", "name"])
    for bad in ("resident_name", "household_income", "phone_number", "home_address", "patient_id"):
        with pytest.raises(ValueError):
            assert_no_individual_fields(["zone_id", bad])
