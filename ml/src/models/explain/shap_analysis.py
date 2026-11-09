"""
HeatSafe-ML Model 1 explanations (Phase 6): global and per-season SHAP importance.

Uses LightGBM's exact TreeSHAP (`pred_contrib=True`), so no extra dependency is needed.
"""

from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd


def shap_importance(model: lgb.LGBMRegressor, frame: pd.DataFrame, features: list[str],
                    group: str = "season") -> dict[str, Any]:
    """
    Mean absolute SHAP value per feature, overall and per group.

    Args:
        model (lgb.LGBMRegressor): Fitted point model.
        frame (pd.DataFrame): Rows to explain (a sample is enough).
        features (list[str]): Model feature names in training order.
        group (str): Grouping column.

    Returns:
        dict[str, Any]: {"overall": {feature: mean|SHAP|}, "<group>": {...}} sorted descending.
    """
    contributions = model.predict(frame[features], pred_contrib=True)[:, :-1]  # last column = bias
    abs_contrib = pd.DataFrame(np.abs(contributions), columns=features, index=frame.index)

    def ranked(rows: pd.DataFrame) -> dict[str, float]:
        """
        Average absolute contributions and sort them.
        """
        means = rows.mean().sort_values(ascending=False)
        return {name: round(float(value), 4) for name, value in means.items()}

    result: dict[str, Any] = {"overall": ranked(abs_contrib)}
    for value, index in frame.groupby(group).groups.items():
        result[str(value)] = ranked(abs_contrib.loc[index])
    return result


def plot_importance(importance: dict[str, Any], path: Path) -> None:
    """
    Save a horizontal bar chart of overall mean |SHAP|.

    Args:
        importance (dict[str, Any]): Output of `shap_importance`.
        path (Path): PNG destination.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    overall = importance["overall"]
    names = list(overall)[::-1]
    fig, ax = plt.subplots(figsize=(7, 6), dpi=120)
    ax.barh(names, [overall[n] for n in names], color="#c2410c")
    ax.set_xlabel("Mean |SHAP| (°C contribution to LST anomaly)")
    ax.set_title("Model 1 drivers of land-surface temperature (all seasons)")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
