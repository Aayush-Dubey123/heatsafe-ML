"""
HeatSafe-ML evaluation metrics (Phase 5+): RMSE, MAE, bias, R², Spearman — overall and per season.
"""

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """
    Compute standard regression scores for LST predictions.

    Bias is mean(prediction − truth): positive means the model runs hot.

    Args:
        y_true (np.ndarray): Observed LST (°C).
        y_pred (np.ndarray): Predicted LST (°C).

    Returns:
        dict[str, float]: rmse, mae, bias, r2, spearman, n.

    Raises:
        ValueError: If inputs differ in length or are empty after dropping NaNs.
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    if y_true.shape != y_pred.shape:
        raise ValueError("y_true and y_pred must have the same shape")
    keep = np.isfinite(y_true) & np.isfinite(y_pred)
    if not keep.any():
        raise ValueError("No finite prediction/observation pairs")
    t, p = y_true[keep], y_pred[keep]
    err = p - t
    ss_res = float(np.sum(err**2))
    ss_tot = float(np.sum((t - t.mean()) ** 2))
    rho = spearmanr(t, p).statistic if t.size > 2 else np.nan
    return {
        "rmse": float(np.sqrt(np.mean(err**2))),
        "mae": float(np.mean(np.abs(err))),
        "bias": float(np.mean(err)),
        "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        "spearman": float(rho),
        "n": int(t.size),
    }


def metrics_by_group(frame: pd.DataFrame, truth: str, prediction: str, group: str = "season") -> dict[str, Any]:
    """
    Score predictions overall and for every value of a grouping column.

    Args:
        frame (pd.DataFrame): Rows holding truth, prediction, and group columns.
        truth (str): Observed LST column.
        prediction (str): Predicted LST column.
        group (str): Grouping column (default: season).

    Returns:
        dict[str, Any]: {"overall": {...}, "<group value>": {...}, ...}.
    """
    result: dict[str, Any] = {"overall": regression_metrics(frame[truth].to_numpy(), frame[prediction].to_numpy())}
    for value, part in frame.groupby(group):
        result[str(value)] = regression_metrics(part[truth].to_numpy(), part[prediction].to_numpy())
    return result
