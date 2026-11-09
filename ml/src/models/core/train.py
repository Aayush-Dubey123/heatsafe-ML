"""
HeatSafe-ML Model 1 training (Phase 6): LightGBM LST model with spatial-block CV.

The model predicts each pixel's LST anomaly relative to its scene anchor (mean LST
of the scene's training-fold pixels), so it learns the spatial pattern rather than
day-to-day weather. An optional second stage interpolates training residuals per
scene (regression kriging via IDW). Every fold uses training-fold rows only.

Usage:
    python -m ml.src.models.core.train
"""

import itertools
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml

from ml.src.commons.logger import get_ml_logger
from ml.src.models.baseline.baselines import idw

logging = get_ml_logger(__name__)

MODEL_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "model.yaml"


def load_model_config() -> dict[str, Any]:
    """
    Load the Model 1 configuration.

    Returns:
        dict[str, Any]: Parsed `ml/configs/model.yaml` → `model1` section.
    """
    with open(MODEL_CONFIG_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)["model1"]


def feature_names(cfg: dict[str, Any]) -> list[str]:
    """
    Flatten the configured feature groups into one ordered list.

    Args:
        cfg (dict[str, Any]): Model 1 configuration.

    Returns:
        list[str]: Feature column names.
    """
    return list(itertools.chain.from_iterable(cfg["features"].values()))


def add_derived_features(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Add circular aspect encodings (flat cells, aspect < 0, encode as 0/0).

    Args:
        frame (pd.DataFrame): Rows with an `aspect` column in degrees.

    Returns:
        pd.DataFrame: Copy with `aspect_sin` and `aspect_cos`.
    """
    out = frame.copy()
    radians = np.deg2rad(out["aspect"].to_numpy(dtype=np.float64))
    flat = out["aspect"].to_numpy() < 0
    out["aspect_sin"] = np.where(flat, 0.0, np.sin(radians)).astype(np.float32)
    out["aspect_cos"] = np.where(flat, 0.0, np.cos(radians)).astype(np.float32)
    return out


def attach_scene_anchor(train: pd.DataFrame, target: pd.DataFrame) -> np.ndarray:
    """
    Look up each target row's scene anchor from training rows only.

    Falls back to the training season mean when a scene has no training rows.

    Args:
        train (pd.DataFrame): Training rows (source of anchors).
        target (pd.DataFrame): Rows that need an anchor.

    Returns:
        np.ndarray: Anchor LST (°C) per target row.
    """
    scene_mean = train.groupby("scene_id")["lst_celsius"].mean()
    season_mean = train.groupby("season")["lst_celsius"].mean()
    anchor = target["scene_id"].map(scene_mean)
    anchor = anchor.fillna(target["season"].map(season_mean)).fillna(float(train["lst_celsius"].mean()))
    return anchor.to_numpy(dtype=np.float64)


def lgbm_params(cfg: dict[str, Any], overrides: dict[str, Any] | None = None,
                objective: str = "regression", alpha: float | None = None) -> dict[str, Any]:
    """
    Assemble LightGBM parameters with a fixed seed.

    Args:
        cfg (dict[str, Any]): Model 1 configuration.
        overrides (dict[str, Any] | None): Tuned values replacing defaults.
        objective (str): "regression" or "quantile".
        alpha (float | None): Quantile level for the quantile objective.

    Returns:
        dict[str, Any]: Keyword arguments for `lgb.LGBMRegressor`.
    """
    params = {**cfg["lightgbm_defaults"], **(overrides or {})}
    params.update({"objective": objective, "random_state": int(cfg["random_seed"]), "deterministic": True,
                   "force_row_wise": True})
    if alpha is not None:
        params["alpha"] = alpha
    return params


def fit_fold_models(train: pd.DataFrame, cfg: dict[str, Any], overrides: dict[str, Any] | None,
                    with_intervals: bool = True) -> dict[str, lgb.LGBMRegressor]:
    """
    Fit the point model (and quantile models) on one training set.

    Args:
        train (pd.DataFrame): Training rows with features and `scene_anchor_lst`.
        cfg (dict[str, Any]): Model 1 configuration.
        overrides (dict[str, Any] | None): Tuned hyper-parameters.
        with_intervals (bool): Also fit lower/upper quantile models.

    Returns:
        dict[str, lgb.LGBMRegressor]: "point" and optionally "lower"/"upper" models.
    """
    features = feature_names(cfg)
    x = train[features]
    y = train["lst_celsius"].to_numpy(dtype=np.float64) - train["scene_anchor_lst"].to_numpy(dtype=np.float64)
    models = {"point": lgb.LGBMRegressor(**lgbm_params(cfg, overrides)).fit(x, y)}
    if with_intervals:
        bounds = (("lower", cfg["intervals"]["lower_quantile"]), ("upper", cfg["intervals"]["upper_quantile"]))
        for name, alpha in bounds:
            models[name] = lgb.LGBMRegressor(**lgbm_params(cfg, overrides, "quantile", float(alpha))).fit(x, y)
    return models


def residual_correction(train: pd.DataFrame, train_pred: np.ndarray, target: pd.DataFrame,
                        k: int, power: float) -> np.ndarray:
    """
    Interpolate training residuals per scene onto target rows (regression kriging via IDW).

    Args:
        train (pd.DataFrame): Training rows.
        train_pred (np.ndarray): Model predictions for the training rows (°C).
        target (pd.DataFrame): Rows to correct.
        k (int): IDW neighbours.
        power (float): IDW distance exponent.

    Returns:
        np.ndarray: Additive correction per target row (0 where the scene has no training rows).
    """
    correction = np.zeros(len(target), dtype=np.float64)
    residual = train["lst_celsius"].to_numpy(dtype=np.float64) - train_pred
    grouped = train.assign(_res=residual).groupby("scene_id")
    scene_ids = target["scene_id"].to_numpy()
    for scene_id in np.unique(scene_ids):
        if scene_id not in grouped.groups:
            continue
        rows = np.flatnonzero(scene_ids == scene_id)
        group = grouped.get_group(scene_id)
        correction[rows] = idw(
            group[["easting", "northing"]].to_numpy(dtype=np.float64), group["_res"].to_numpy(),
            target.iloc[rows][["easting", "northing"]].to_numpy(dtype=np.float64), k, power,
        )
    return correction


def predict_fold(models: dict[str, lgb.LGBMRegressor], train: pd.DataFrame, valid: pd.DataFrame,
                 cfg: dict[str, Any]) -> pd.DataFrame:
    """
    Predict validation rows: point, kriged point, and 90% interval bounds.

    Interval bounds are shifted by the same kriging correction as the point estimate
    (the correction moves the centre; it does not change the predicted spread).

    Args:
        models (dict[str, lgb.LGBMRegressor]): Output of `fit_fold_models`.
        train (pd.DataFrame): Training rows (for residual kriging).
        valid (pd.DataFrame): Validation rows.
        cfg (dict[str, Any]): Model 1 configuration.

    Returns:
        pd.DataFrame: Columns pred_lgbm, pred_rk, lower, upper, lower_rk, upper_rk.
    """
    features = feature_names(cfg)
    rk = cfg["residual_kriging"]
    anchor_valid = valid["scene_anchor_lst"].to_numpy(dtype=np.float64)
    anchor_train = train["scene_anchor_lst"].to_numpy(dtype=np.float64)
    point = anchor_valid + models["point"].predict(valid[features])
    train_point = anchor_train + models["point"].predict(train[features])
    correction = residual_correction(train, train_point, valid, int(rk["idw_neighbours"]), float(rk["idw_power"]))
    out = pd.DataFrame({"pred_lgbm": point, "pred_rk": point + correction}, index=valid.index)
    if "lower" in models:
        lower = anchor_valid + models["lower"].predict(valid[features])
        upper = anchor_valid + models["upper"].predict(valid[features])
        lower, upper = np.minimum(lower, upper), np.maximum(lower, upper)
        out["lower"], out["upper"] = lower, upper
        out["lower_rk"], out["upper_rk"] = lower + correction, upper + correction
    return out


def cross_validate_model1(table: pd.DataFrame, cfg: dict[str, Any], overrides: dict[str, Any] | None,
                          with_intervals: bool = True) -> pd.DataFrame:
    """
    Out-of-fold predictions for Model 1 across the spatial-block folds.

    Args:
        table (pd.DataFrame): CV-eligible rows (see baselines.cv_eligible) with derived features.
        cfg (dict[str, Any]): Model 1 configuration.
        overrides (dict[str, Any] | None): Tuned hyper-parameters.
        with_intervals (bool): Also produce interval predictions.

    Returns:
        pd.DataFrame: Validation rows with truth, fold metadata, and prediction columns.
    """
    parts = []
    for fold in sorted(table["fold"].unique()):
        train = table[table["fold"] != fold].copy()
        valid = table[table["fold"] == fold].copy()
        assert set(train["block_id"]).isdisjoint(set(valid["block_id"])), "spatial leakage between folds"  # noqa: S101
        train["scene_anchor_lst"] = attach_scene_anchor(train, train)
        valid["scene_anchor_lst"] = attach_scene_anchor(train, valid)
        models = fit_fold_models(train, cfg, overrides, with_intervals)
        preds = predict_fold(models, train, valid, cfg)
        parts.append(pd.concat([valid[["fold", "season", "scene_id", "block_id", "lst_celsius"]], preds], axis=1))
        logging.info(f"Model 1 fold {fold}: trained on {len(train):,} rows, validated on {len(valid):,}")
    return pd.concat(parts, ignore_index=True)


def tune_hyperparameters(table: pd.DataFrame, cfg: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Random search over the configured space with a small spatial-block CV on a row sample.

    Inner folds regroup the outer folds (fold % inner_folds), so tuning also respects
    block boundaries. The final score is still produced by the full 5-fold CV.

    Args:
        table (pd.DataFrame): CV-eligible rows with derived features.
        cfg (dict[str, Any]): Model 1 configuration.

    Returns:
        tuple[dict[str, Any], list[dict[str, Any]]]: Best overrides and the full trial log.
    """
    tuning = cfg["tuning"]
    rng = np.random.default_rng(int(cfg["random_seed"]))
    sample = table.sample(n=min(int(tuning["sample_rows"]), len(table)), random_state=int(cfg["random_seed"])).copy()
    sample["fold"] = sample["fold"] % int(tuning["inner_folds"])
    space = tuning["search_space"]
    trials: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for trial in range(int(tuning["n_trials"])):
        overrides = {name: values[int(rng.integers(len(values)))] for name, values in space.items()}
        key = tuple(sorted(overrides.items()))
        if key in seen:
            continue
        seen.add(key)
        oof = cross_validate_model1(sample, cfg, overrides, with_intervals=False)
        rmse = float(np.sqrt(np.mean((oof["pred_lgbm"] - oof["lst_celsius"]) ** 2)))
        trials.append({"trial": trial, "params": overrides, "rmse": rmse})
        logging.info(f"Tuning trial {trial}: rmse={rmse:.3f} params={overrides}")
    best = min(trials, key=lambda t: t["rmse"])
    return best["params"], trials


def fit_random_forest_comparison(table: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """
    Spatial-CV out-of-fold predictions from a Random Forest on a row sample (comparison only).

    Args:
        table (pd.DataFrame): CV-eligible rows with derived features.
        cfg (dict[str, Any]): Model 1 configuration.

    Returns:
        pd.DataFrame: Validation rows with `pred_rf`.
    """
    from sklearn.ensemble import RandomForestRegressor

    rf_cfg = cfg["random_forest_comparison"]
    sample = table.sample(n=min(int(rf_cfg["sample_rows"]), len(table)), random_state=int(cfg["random_seed"]))
    features = feature_names(cfg)
    parts = []
    for fold in sorted(sample["fold"].unique()):
        train = sample[sample["fold"] != fold].copy()
        valid = sample[sample["fold"] == fold].copy()
        train["scene_anchor_lst"] = attach_scene_anchor(train, train)
        valid["scene_anchor_lst"] = attach_scene_anchor(train, valid)
        model = RandomForestRegressor(
            n_estimators=int(rf_cfg["n_estimators"]), max_depth=int(rf_cfg["max_depth"]),
            min_samples_leaf=int(rf_cfg["min_samples_leaf"]), n_jobs=-1, random_state=int(cfg["random_seed"]),
        )
        model.fit(train[features].fillna(0.0), train["lst_celsius"] - train["scene_anchor_lst"])
        valid["pred_rf"] = valid["scene_anchor_lst"] + model.predict(valid[features].fillna(0.0))
        parts.append(valid[["fold", "season", "scene_id", "lst_celsius", "pred_rf"]])
    return pd.concat(parts, ignore_index=True)
