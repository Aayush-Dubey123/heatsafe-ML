import numpy as np
import pandas as pd
import pytest

from ml.src.models.baseline.baselines import cross_validate_baselines, cv_eligible, idw
from ml.src.models.baseline.metrics import metrics_by_group, regression_metrics


def test_regression_metrics_known_values():
    """
    RMSE, MAE, bias, and R² match hand-computed values; NaN pairs are dropped.
    """
    m = regression_metrics(np.array([1.0, 2.0, 3.0, np.nan]), np.array([2.0, 2.0, 4.0, 5.0]))
    assert m["n"] == 3
    assert m["rmse"] == pytest.approx(np.sqrt(2 / 3))
    assert m["mae"] == pytest.approx(2 / 3)
    assert m["bias"] == pytest.approx(2 / 3)
    assert m["r2"] == pytest.approx(1 - 2 / 2)


def test_regression_metrics_rejects_mismatched_input():
    """
    Shape mismatches and all-NaN inputs raise errors.
    """
    with pytest.raises(ValueError):
        regression_metrics(np.array([1.0]), np.array([1.0, 2.0]))
    with pytest.raises(ValueError):
        regression_metrics(np.array([np.nan]), np.array([1.0]))


def test_idw_reproduces_value_at_training_point():
    """
    IDW returns the training value when the query sits on a training point.
    """
    xy = np.array([[0.0, 0.0], [100.0, 0.0], [0.0, 100.0]])
    values = np.array([1.0, 5.0, 9.0])
    # distances are floored at 1 m, so the match is approximate
    assert idw(xy, values, np.array([[0.0, 0.0]]), k=3, power=2.0)[0] == pytest.approx(1.0, abs=1e-2)


def synthetic_table(seed: int = 0) -> pd.DataFrame:
    """
    Build a table where LST = scene offset + linear drivers + smooth spatial residual.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(12):
        season = ["summer", "winter", "monsoon", "post-monsoon"][s % 4]
        offset = {"summer": 44, "winter": 28, "monsoon": 32, "post-monsoon": 33}[season] + rng.normal(0, 2)
        n = 1500
        easting = rng.uniform(0, 20000, n)
        northing = rng.uniform(0, 20000, n)
        ndvi = rng.uniform(0, 0.8, n)
        smooth = 2.0 * np.sin(easting / 3000) * np.cos(northing / 4000)
        bx, by = (easting // 2000).astype(int), (northing // 2000).astype(int)
        rows.append(pd.DataFrame({
            "scene_id": f"S{s}", "season": season, "split": "train",
            "easting": easting, "northing": northing,
            "block_id": [f"B_{x:02d}_{y:02d}" for x, y in zip(bx, by, strict=True)],
            "ndvi": ndvi, "ndbi": -0.5 * ndvi, "mndwi": rng.normal(-0.4, 0.05, n),
            "elevation": rng.normal(300, 10, n),
            "lst_celsius": offset - 10 * ndvi + smooth + rng.normal(0, 0.3, n),
        }))
    table = pd.concat(rows, ignore_index=True)
    blocks = sorted(table["block_id"].unique())
    fold_of = {b: i % 5 for i, b in enumerate(blocks)}
    table["fold"] = table["block_id"].map(fold_of).astype(np.int8)
    table["is_holdout_block"] = False
    return table


def test_baselines_rank_as_expected_and_no_block_leakage():
    """
    On structured synthetic data B3 < B2 < B1 in RMSE, and validation blocks never train.
    """
    table = synthetic_table()
    oof = cross_validate_baselines(table, k=12, power=2.0)
    assert len(oof) == len(table)

    for fold in oof["fold"].unique():
        valid_blocks = set(oof.loc[oof["fold"] == fold, "block_id"])
        train_blocks = set(table.loc[table["fold"] != fold, "block_id"])
        assert valid_blocks.isdisjoint(train_blocks)

    rmse = {b: metrics_by_group(oof, "lst_celsius", b)["overall"]["rmse"] for b in ("b1", "b2", "b3")}
    assert rmse["b3"] < rmse["b2"] < rmse["b1"]
    assert rmse["b3"] < 1.0


def test_cv_eligible_excludes_holdout_blocks_and_test_year():
    """
    Holdout blocks and 2026 test-year rows never reach cross-validation.
    """
    table = pd.DataFrame({
        "split": ["train", "train", "test_year", "train"],
        "is_holdout_block": [False, True, False, False],
        "fold": [0, -1, 2, 3],
    })
    assert cv_eligible(table)["fold"].tolist() == [0, 3]
