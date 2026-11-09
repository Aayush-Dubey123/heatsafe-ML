import copy

import numpy as np
import pandas as pd
import pytest

from ml.src.models.baseline.baselines import cross_validate_baselines
from ml.src.models.baseline.metrics import regression_metrics
from ml.src.models.core.evaluate import phase6_gate
from ml.src.models.core.train import (
    add_derived_features,
    attach_scene_anchor,
    cross_validate_model1,
    feature_names,
    fit_fold_models,
    load_model_config,
)
from ml.src.models.explain.intervals import interval_coverage
from ml.src.models.explain.shap_analysis import shap_importance


def small_config() -> dict:
    """
    Real Model 1 config with a tiny, fast LightGBM for unit tests.
    """
    cfg = copy.deepcopy(load_model_config())
    cfg["lightgbm_defaults"].update({"n_estimators": 60, "num_leaves": 15, "learning_rate": 0.1, "n_jobs": 2})
    return cfg


def synthetic_model_table(seed: int = 0, scenes: int = 8, rows_per_scene: int = 1200) -> pd.DataFrame:
    """
    Rows with every Model 1 feature; LST = scene level − 10·NDVI + 6·NDBI_450m + noise.
    """
    rng = np.random.default_rng(seed)
    parts = []
    for s in range(scenes):
        season = ["summer", "winter"][s % 2]
        level = (44 if season == "summer" else 28) + rng.normal(0, 2)
        n = rows_per_scene
        easting, northing = rng.uniform(0, 20000, n), rng.uniform(0, 20000, n)
        ndvi = rng.uniform(0, 0.8, n)
        ndbi_450 = rng.uniform(-0.3, 0.3, n)
        bx, by = (easting // 2000).astype(int), (northing // 2000).astype(int)
        parts.append(pd.DataFrame({
            "scene_id": f"S{s}", "season": season, "split": "train", "is_holdout_block": False,
            "easting": easting, "northing": northing,
            "block_id": [f"B_{x:02d}_{y:02d}" for x, y in zip(bx, by, strict=True)],
            "elevation": rng.normal(300, 10, n), "slope": rng.uniform(0, 5, n), "aspect": rng.uniform(-1, 360, n),
            "ndvi": ndvi, "ndbi": rng.uniform(-0.3, 0.3, n), "mndwi": rng.normal(-0.4, 0.05, n),
            "ndvi_150m": ndvi + rng.normal(0, 0.02, n), "ndvi_450m": ndvi + rng.normal(0, 0.05, n),
            "ndbi_150m": ndbi_450 + rng.normal(0, 0.02, n), "ndbi_450m": ndbi_450,
            "mndwi_150m": rng.normal(-0.4, 0.05, n), "mndwi_450m": rng.normal(-0.4, 0.05, n),
            "sin_doy": np.float32(np.sin(s)), "cos_doy": np.float32(np.cos(s)),
            "mean_solar_hour": rng.normal(10.4, 0.01, n),
            "lst_celsius": level - 10 * ndvi + 6 * ndbi_450 + rng.normal(0, 0.4, n),
        }))
    table = pd.concat(parts, ignore_index=True)
    blocks = sorted(table["block_id"].unique())
    table["fold"] = table["block_id"].map({b: i % 5 for i, b in enumerate(blocks)}).astype(np.int8)
    return add_derived_features(table)


def test_aspect_encoding_handles_flat_cells():
    """
    Flat cells (aspect −1) encode as (0, 0); east-facing (90°) as (1, 0).
    """
    out = add_derived_features(pd.DataFrame({"aspect": [-1.0, 90.0]}))
    assert out["aspect_sin"].tolist() == pytest.approx([0.0, 1.0])
    assert out["aspect_cos"].tolist() == pytest.approx([0.0, 0.0], abs=1e-6)


def test_scene_anchor_uses_training_rows_only():
    """
    Leakage guard: changing validation LST never changes the validation anchor.
    """
    train = pd.DataFrame({"scene_id": ["A", "A"], "season": ["summer"] * 2, "lst_celsius": [40.0, 42.0]})
    valid = pd.DataFrame({"scene_id": ["A", "B"], "season": ["summer", "summer"], "lst_celsius": [99.0, 99.0]})
    before = attach_scene_anchor(train, valid)
    valid["lst_celsius"] = [-50.0, -50.0]
    after = attach_scene_anchor(train, valid)
    assert before.tolist() == after.tolist() == [41.0, 41.0]


def test_model1_cv_has_zero_block_leakage_and_beats_scene_mean_baseline():
    """
    No block appears in both training and validation; Model 1 beats Baseline 2 on structured data.
    """
    table = synthetic_model_table()
    cfg = small_config()
    oof = cross_validate_model1(table, cfg, overrides=None, with_intervals=True)
    for fold in oof["fold"].unique():
        valid_blocks = set(oof.loc[oof["fold"] == fold, "block_id"])
        assert valid_blocks.isdisjoint(set(table.loc[table["fold"] != fold, "block_id"]))

    base = cross_validate_baselines(table, k=12, power=2.0)
    model_rmse = regression_metrics(oof["lst_celsius"], oof["pred_lgbm"])["rmse"]
    b2_rmse = regression_metrics(base["lst_celsius"], base["b2"])["rmse"]
    assert model_rmse < 0.5 * b2_rmse
    assert (oof["upper"] >= oof["lower"]).all()
    coverage = interval_coverage(oof["lst_celsius"], oof["lower"], oof["upper"])["coverage"]
    assert 0.6 < coverage <= 1.0


def test_shap_identifies_the_true_driver():
    """
    On data where NDVI dominates, NDVI is the top SHAP feature.
    """
    table = synthetic_model_table(scenes=4)
    cfg = small_config()
    table["scene_anchor_lst"] = attach_scene_anchor(table, table)
    models = fit_fold_models(table, cfg, None, with_intervals=False)
    importance = shap_importance(models["point"], table.sample(2000, random_state=0), feature_names(cfg))
    assert next(iter(importance["overall"])) in {"ndvi", "ndvi_150m", "ndvi_450m"}


def test_interval_coverage_math():
    """
    Coverage counts inclusive bounds and width is averaged.
    """
    result = interval_coverage(np.array([1.0, 2.0, 5.0]), np.array([0.0, 2.0, 0.0]), np.array([2.0, 3.0, 4.0]))
    assert result["coverage"] == pytest.approx(2 / 3)
    assert result["mean_width"] == pytest.approx((2 + 1 + 4) / 3)


@pytest.mark.parametrize("rmse,coverage,passed", [(0.80, 0.90, True), (0.90, 0.90, False), (0.80, 0.80, False)])
def test_phase6_gate(rmse, coverage, passed):
    """
    The gate needs both ≥15% RMSE improvement over Baseline 3 and ≥85% coverage.
    """
    assert phase6_gate(rmse, 1.0, coverage, 0.15, 0.85)["passed"] is passed
