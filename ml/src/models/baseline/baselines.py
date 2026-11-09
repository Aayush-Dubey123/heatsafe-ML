"""
HeatSafe-ML baseline models (Phase 5) — the bar Model 1 must beat.

All baselines are scored with 5-fold spatial-block cross-validation (D5) on
training-window rows outside the fixed holdout blocks; the test set is untouched.

  Baseline 1  per-season city mean LST from training folds.
  Baseline 2  per-scene city mean LST of the scene's training-fold pixels
              (replaces per-pixel climatology, which is undefined for held-out
              blocks under spatial CV — Decision D11).
  Baseline 3  pooled OLS on NDVI, NDBI, MNDWI, elevation + per-scene IDW
              interpolation of training-fold residuals.

Usage:
    python -m ml.src.models.baseline.baselines
"""

import json
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from ml.src.commons.logger import get_ml_logger
from ml.src.dataset.build import PROCESSED_DIR, TRAINING_TABLE
from ml.src.dataset.splits import load_thresholds
from ml.src.models.baseline.metrics import metrics_by_group

logging = get_ml_logger(__name__)

OLS_FEATURES = ("ndvi", "ndbi", "mndwi", "elevation")
BASELINE_DIR = PROCESSED_DIR / "baselines"


def predict_baseline1(train: pd.DataFrame, valid: pd.DataFrame) -> np.ndarray:
    """
    Predict each validation row with its season's mean training LST.

    Args:
        train (pd.DataFrame): Training-fold rows.
        valid (pd.DataFrame): Validation-fold rows.

    Returns:
        np.ndarray: Predictions aligned with `valid`.
    """
    season_mean = train.groupby("season")["lst_celsius"].mean()
    fallback = float(train["lst_celsius"].mean())
    return valid["season"].map(season_mean).fillna(fallback).to_numpy(dtype=np.float64)


def predict_baseline2(train: pd.DataFrame, valid: pd.DataFrame) -> np.ndarray:
    """
    Predict each validation row with the mean training-fold LST of the same scene.

    Args:
        train (pd.DataFrame): Training-fold rows.
        valid (pd.DataFrame): Validation-fold rows.

    Returns:
        np.ndarray: Predictions aligned with `valid` (season mean when a scene has no training rows).
    """
    scene_mean = train.groupby("scene_id")["lst_celsius"].mean()
    fallback = pd.Series(predict_baseline1(train, valid), index=valid.index)
    return valid["scene_id"].map(scene_mean).fillna(fallback).to_numpy(dtype=np.float64)


def fit_ols(train: pd.DataFrame) -> np.ndarray:
    """
    Fit pooled ordinary least squares of LST on the Baseline 3 drivers.

    Args:
        train (pd.DataFrame): Training-fold rows.

    Returns:
        np.ndarray: Coefficients [intercept, *OLS_FEATURES].
    """
    design = np.column_stack([np.ones(len(train)), train[list(OLS_FEATURES)].to_numpy(dtype=np.float64)])
    coef, *_ = np.linalg.lstsq(design, train["lst_celsius"].to_numpy(dtype=np.float64), rcond=None)
    return coef


def ols_predict(coef: np.ndarray, frame: pd.DataFrame) -> np.ndarray:
    """
    Apply OLS coefficients to rows.

    Args:
        coef (np.ndarray): Output of `fit_ols`.
        frame (pd.DataFrame): Rows with OLS_FEATURES.

    Returns:
        np.ndarray: Linear predictions.
    """
    return coef[0] + frame[list(OLS_FEATURES)].to_numpy(dtype=np.float64) @ coef[1:]


def idw(train_xy: np.ndarray, train_values: np.ndarray, query_xy: np.ndarray, k: int, power: float) -> np.ndarray:
    """
    Inverse-distance-weighted interpolation from the k nearest training points.

    Args:
        train_xy (np.ndarray): (n, 2) training coordinates in metres.
        train_values (np.ndarray): Values at training points.
        query_xy (np.ndarray): (m, 2) query coordinates.
        k (int): Number of neighbours.
        power (float): Distance exponent.

    Returns:
        np.ndarray: Interpolated values for the query points.
    """
    k = min(k, len(train_xy))
    distances, indices = cKDTree(train_xy).query(query_xy, k=k)
    if k == 1:
        distances, indices = distances[:, None], indices[:, None]
    weights = 1.0 / np.maximum(distances, 1.0) ** power
    return np.sum(weights * train_values[indices], axis=1) / np.sum(weights, axis=1)


def predict_baseline3(train: pd.DataFrame, valid: pd.DataFrame, k: int, power: float) -> np.ndarray:
    """
    Pooled OLS prediction plus per-scene IDW interpolation of training residuals.

    Args:
        train (pd.DataFrame): Training-fold rows.
        valid (pd.DataFrame): Validation-fold rows.
        k (int): IDW neighbours.
        power (float): IDW distance exponent.

    Returns:
        np.ndarray: Predictions aligned with `valid`.
    """
    coef = fit_ols(train)
    train_residual = train["lst_celsius"].to_numpy(dtype=np.float64) - ols_predict(coef, train)
    prediction = ols_predict(coef, valid)
    train_by_scene = train.assign(_res=train_residual).groupby("scene_id")
    positions = {sid: np.flatnonzero(valid["scene_id"].to_numpy() == sid) for sid in valid["scene_id"].unique()}
    for scene_id, rows in positions.items():
        if scene_id not in train_by_scene.groups:
            continue
        group = train_by_scene.get_group(scene_id)
        prediction[rows] += idw(
            group[["easting", "northing"]].to_numpy(dtype=np.float64), group["_res"].to_numpy(),
            valid.iloc[rows][["easting", "northing"]].to_numpy(dtype=np.float64), k, power,
        )
    return prediction


def cross_validate_baselines(table: pd.DataFrame, k: int, power: float) -> pd.DataFrame:
    """
    Produce out-of-fold predictions for all three baselines.

    Args:
        table (pd.DataFrame): CV-eligible rows (training window, non-holdout).
        k (int): IDW neighbours.
        power (float): IDW distance exponent.

    Returns:
        pd.DataFrame: Rows with fold, season, scene_id, lst_celsius and b1/b2/b3 predictions.
    """
    parts = []
    for fold in sorted(table["fold"].unique()):
        train, valid = table[table["fold"] != fold], table[table["fold"] == fold].copy()
        valid["b1"] = predict_baseline1(train, valid)
        valid["b2"] = predict_baseline2(train, valid)
        valid["b3"] = predict_baseline3(train, valid, k, power)
        parts.append(valid[["fold", "season", "scene_id", "block_id", "lst_celsius", "b1", "b2", "b3"]])
        logging.info(f"Fold {fold}: {len(train):,} train rows, {len(valid):,} validation rows")
    return pd.concat(parts, ignore_index=True)


def cv_eligible(table: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only rows allowed in cross-validation: training window and non-holdout blocks.

    Args:
        table (pd.DataFrame): Full training table.

    Returns:
        pd.DataFrame: CV-eligible rows.
    """
    keep = (table["split"] == "train") & (~table["is_holdout_block"]) & (table["fold"] >= 0)
    return table[keep].reset_index(drop=True)


def run_baselines() -> dict[str, Any]:
    """
    Cross-validate the baselines and save the locked score table.

    Returns:
        dict[str, Any]: {"baseline_1": metrics, "baseline_2": ..., "baseline_3": ..., "rows": n}.
    """
    cfg = load_thresholds()["baselines"]
    table = cv_eligible(pd.read_parquet(TRAINING_TABLE))
    oof = cross_validate_baselines(table, int(cfg["idw_neighbours"]), float(cfg["idw_power"]))
    scores = {
        "baseline_1": metrics_by_group(oof, "lst_celsius", "b1"),
        "baseline_2": metrics_by_group(oof, "lst_celsius", "b2"),
        "baseline_3": metrics_by_group(oof, "lst_celsius", "b3"),
        "rows": int(len(oof)),
        "scenes": int(oof["scene_id"].nunique()),
        "folds": int(oof["fold"].nunique()),
    }
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    (BASELINE_DIR / "baseline_scores.json").write_text(json.dumps(scores, indent=2), encoding="utf-8")
    oof.to_parquet(BASELINE_DIR / "baseline_oof.parquet", index=False)
    return scores


def score_table(scores: dict[str, Any]) -> pd.DataFrame:
    """
    Flatten baseline scores into a metric × baseline × season table.

    Args:
        scores (dict[str, Any]): Output of `run_baselines`.

    Returns:
        pd.DataFrame: Long-form score table.
    """
    rows = []
    for baseline in ("baseline_1", "baseline_2", "baseline_3"):
        for group, metrics in scores[baseline].items():
            rows.append({"baseline": baseline, "season": group, **{k: round(v, 3) if isinstance(v, float) else v
                                                                    for k, v in metrics.items()}})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    result = run_baselines()
    print(score_table(result).to_string(index=False))
