"""
HeatSafe-ML prediction-interval diagnostics (Phase 6): empirical coverage and width.
"""

from typing import Any

import numpy as np
import pandas as pd


def interval_coverage(truth: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> dict[str, float]:
    """
    Share of observations inside [lower, upper] and the mean interval width.

    Args:
        truth (np.ndarray): Observed LST (°C).
        lower (np.ndarray): Lower bounds.
        upper (np.ndarray): Upper bounds.

    Returns:
        dict[str, float]: coverage (0–1), mean_width (°C), n.

    Raises:
        ValueError: If no finite triples exist.
    """
    t, lo, hi = (np.asarray(a, dtype=np.float64) for a in (truth, lower, upper))
    keep = np.isfinite(t) & np.isfinite(lo) & np.isfinite(hi)
    if not keep.any():
        raise ValueError("No finite interval triples")
    inside = (t[keep] >= lo[keep]) & (t[keep] <= hi[keep])
    return {"coverage": float(inside.mean()), "mean_width": float(np.mean(hi[keep] - lo[keep])), "n": int(keep.sum())}


def coverage_by_group(frame: pd.DataFrame, lower: str, upper: str, group: str = "season") -> dict[str, Any]:
    """
    Interval coverage overall and per group.

    Args:
        frame (pd.DataFrame): Rows with `lst_celsius`, lower, and upper columns.
        lower (str): Lower-bound column.
        upper (str): Upper-bound column.
        group (str): Grouping column.

    Returns:
        dict[str, Any]: {"overall": {...}, "<group>": {...}}.
    """
    result: dict[str, Any] = {"overall": interval_coverage(frame["lst_celsius"], frame[lower], frame[upper])}
    for value, part in frame.groupby(group):
        result[str(value)] = interval_coverage(part["lst_celsius"], part[lower], part[upper])
    return result
