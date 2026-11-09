"""
HeatSafe-ML final test-set evaluation (Phase 7) — the test set is opened ONCE (Decision D4).

Test rows are pixels inside the frozen holdout blocks (D5):
  * "test_2026"        2026 scenes x holdout blocks (new time AND new place, primary result)
  * "train_years_holdout"  2019–2025 scenes x holdout blocks (new place only)

For each test scene the model anchor and residual kriging use only that scene's
pixels in non-holdout blocks — exactly what the live service can see. Baseline 3 is
scored the same way. A lock file prevents re-opening the test set and re-tuning.

Usage:
    python -m ml.src.validation.final_test --confirm-open-test-set
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from ml.src.commons.logger import get_ml_logger
from ml.src.dataset.build import PROCESSED_DIR, TRAINING_TABLE
from ml.src.models.baseline.baselines import BASELINE_DIR, predict_baseline3
from ml.src.models.baseline.metrics import regression_metrics
from ml.src.models.core.evaluate import REGISTRY_DIR
from ml.src.models.core.train import (
    add_derived_features,
    attach_scene_anchor,
    feature_names,
    load_model_config,
    residual_correction,
)
from ml.src.models.explain.intervals import interval_coverage

logging = get_ml_logger(__name__)

TEST_DIR = PROCESSED_DIR / "final_test"
LOCK_FILE = TEST_DIR / "test_set_opened.json"


def latest_model_dir(registry: Path = REGISTRY_DIR) -> Path:
    """
    Return the newest Model 1 registry folder.

    Args:
        registry (Path): Registry root.

    Returns:
        Path: Folder containing point/lower/upper models and metadata.json.

    Raises:
        FileNotFoundError: If no model has been registered (run Phase 6 first).
    """
    versions = sorted(p for p in registry.glob("m1-*") if (p / "metadata.json").is_file())
    if not versions:
        raise FileNotFoundError("No registered Model 1 found; run Phase 6 first")
    return versions[-1]


def land_cover_class(frame: pd.DataFrame) -> pd.Series:
    """
    Coarse land-cover proxy from spectral indices (no land-cover map is ingested yet).

    Args:
        frame (pd.DataFrame): Rows with ndvi and ndbi.

    Returns:
        pd.Series: 'vegetation' (NDVI ≥ 0.4), 'built_up' (NDBI > 0), else 'bare_or_mixed'.
    """
    return pd.Series(
        np.where(frame["ndvi"] >= 0.4, "vegetation", np.where(frame["ndbi"] > 0.0, "built_up", "bare_or_mixed")),
        index=frame.index,
    )


def block_bootstrap_ci(frame: pd.DataFrame, prediction: str, n_resamples: int, seed: int) -> dict[str, list[float]]:
    """
    95% confidence intervals for RMSE, MAE, and bias by resampling whole blocks.

    Resampling blocks (not pixels) respects spatial autocorrelation.

    Args:
        frame (pd.DataFrame): Test rows with block_id, lst_celsius, and the prediction column.
        prediction (str): Prediction column.
        n_resamples (int): Bootstrap iterations (≥ 1000 per the plan).
        seed (int): Random seed.

    Returns:
        dict[str, list[float]]: {"rmse": [lo, hi], "mae": [...], "bias": [...]}.
    """
    rng = np.random.default_rng(seed)
    err = (frame[prediction] - frame["lst_celsius"]).to_numpy()
    codes, uniques = pd.factorize(frame["block_id"])
    sums = np.bincount(codes, weights=err**2), np.bincount(codes, weights=np.abs(err)), np.bincount(codes, weights=err)
    counts = np.bincount(codes)
    stats: dict[str, list[float]] = {"rmse": [], "mae": [], "bias": []}
    for _ in range(n_resamples):
        pick = rng.integers(0, len(uniques), len(uniques))
        n = counts[pick].sum()
        stats["rmse"].append(float(np.sqrt(sums[0][pick].sum() / n)))
        stats["mae"].append(float(sums[1][pick].sum() / n))
        stats["bias"].append(float(sums[2][pick].sum() / n))
    return {
        name: [round(float(np.percentile(values, 2.5)), 3), round(float(np.percentile(values, 97.5)), 3)]
        for name, values in stats.items()
    }


def score_test_group(frame: pd.DataFrame, n_resamples: int, seed: int) -> dict[str, Any]:
    """
    Full scorecard for one test group: metrics, CIs, coverage, and error breakdowns.

    Args:
        frame (pd.DataFrame): Test rows with predictions.
        n_resamples (int): Bootstrap iterations.
        seed (int): Random seed.

    Returns:
        dict[str, Any]: Scorecard.
    """
    frame = frame.assign(land_cover=land_cover_class(frame),
                         ndvi_tercile=pd.qcut(frame["ndvi"], 3, labels=["low", "mid", "high"]).astype(str))
    card: dict[str, Any] = {
        "rows": int(len(frame)),
        "scenes": int(frame["scene_id"].nunique()),
        "blocks": int(frame["block_id"].nunique()),
        "model1": regression_metrics(frame["lst_celsius"], frame["pred"]),
        "baseline_3": regression_metrics(frame["lst_celsius"], frame["b3"]),
        "model1_ci95": block_bootstrap_ci(frame, "pred", n_resamples, seed),
        "baseline_3_ci95": block_bootstrap_ci(frame, "b3", n_resamples, seed),
        "interval_coverage": interval_coverage(frame["lst_celsius"], frame["lower"], frame["upper"]),
    }
    for column in ("season", "land_cover", "ndvi_tercile"):
        card[f"by_{column}"] = {
            str(value): {k: round(v, 3) if isinstance(v, float) else v
                         for k, v in regression_metrics(part["lst_celsius"], part["pred"]).items()}
            for value, part in frame.groupby(column) if len(part) > 2
        }
    card["rmse_ratio_vs_baseline_3"] = round(card["model1"]["rmse"] / card["baseline_3"]["rmse"], 4)
    return card


def predict_test_rows(table: pd.DataFrame, model_dir: Path, cfg: dict[str, Any]) -> pd.DataFrame:
    """
    Predict every holdout-block row using only non-holdout pixels of the same scene as context.

    Args:
        table (pd.DataFrame): Training table including test-year rows, with derived features.
        model_dir (Path): Registered model folder.
        cfg (dict[str, Any]): Model 1 configuration.

    Returns:
        pd.DataFrame: Holdout rows with pred, lower, upper, and b3 columns.
    """
    metadata = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
    boosters = {name: lgb.Booster(model_file=str(model_dir / f"{name}.txt")) for name in ("point", "lower", "upper")}
    features = metadata["features"]
    rk = cfg["residual_kriging"]
    context = table[~table["is_holdout_block"]].copy()
    test = table[table["is_holdout_block"]].copy()

    context["scene_anchor_lst"] = attach_scene_anchor(context, context)
    test["scene_anchor_lst"] = attach_scene_anchor(context, test)
    test_pred = test["scene_anchor_lst"].to_numpy() + boosters["point"].predict(test[features])
    correction = np.zeros(len(test))
    if metadata.get("residual_kriging"):
        context_pred = context["scene_anchor_lst"].to_numpy() + boosters["point"].predict(context[features])
        correction = residual_correction(context, context_pred, test, int(rk["idw_neighbours"]), float(rk["idw_power"]))
    lower = test["scene_anchor_lst"].to_numpy() + boosters["lower"].predict(test[features]) + correction
    upper = test["scene_anchor_lst"].to_numpy() + boosters["upper"].predict(test[features]) + correction
    test["pred"] = test_pred + correction
    test["lower"], test["upper"] = np.minimum(lower, upper), np.maximum(lower, upper)
    test["b3"] = predict_baseline3(context, test, int(rk["idw_neighbours"]), float(rk["idw_power"]))
    return test


def open_test_set_once(confirm: bool, n_resamples: int = 1000, seed: int = 20261109) -> dict[str, Any]:
    """
    Evaluate Model 1 on the test set exactly once and record the lock.

    Args:
        confirm (bool): Must be True; guards against accidental runs.
        n_resamples (int): Bootstrap iterations.
        seed (int): Bootstrap seed.

    Returns:
        dict[str, Any]: Final test report.

    Raises:
        PermissionError: If not confirmed or the test set was already opened.
    """
    if not confirm:
        raise PermissionError("Pass --confirm-open-test-set: the test set can only be opened once (D4).")
    if LOCK_FILE.is_file():
        raise PermissionError(f"Test set already opened on {json.loads(LOCK_FILE.read_text())['opened_utc']}; "
                              "re-opening would invalidate the result.")
    cfg = load_model_config()
    model_dir = latest_model_dir()
    table = add_derived_features(pd.read_parquet(TRAINING_TABLE))
    if not (table["split"] == "test_year").any():
        raise RuntimeError("No 2026 rows in training_v2.parquet; rebuild with --include-test-year first")

    TEST_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps({"opened_utc": datetime.now(UTC).isoformat(), "model": model_dir.name}),
                         encoding="utf-8")
    predictions = predict_test_rows(table, model_dir, cfg)
    groups = {
        "test_2026": predictions[predictions["split"] == "test_year"],
        "train_years_holdout": predictions[predictions["split"] == "train"],
    }
    report = {
        "model_version": model_dir.name,
        "opened_utc": json.loads(LOCK_FILE.read_text())["opened_utc"],
        "feature_list": feature_names(cfg),
        "baseline_cv_reference": json.loads(
            (BASELINE_DIR / "baseline_scores.json").read_text(encoding="utf-8")
        )["baseline_3"]["overall"],
        "groups": {name: score_test_group(frame, n_resamples, seed) for name, frame in groups.items() if len(frame)},
        "station_comparison": {
            "status": "not performed",
            "reason": "IMD station records require a formal data request and CPCB CAAQMS data sits behind a "
                      "captcha-protected portal; neither could be retrieved automatically. Validation is LST-only "
                      "(risk register mitigation). Station air temperature is a different variable from LST.",
        },
    }
    (TEST_DIR / "final_test_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    predictions.to_parquet(TEST_DIR / "final_test_predictions.parquet", index=False)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Open the HeatSafe-ML test set once (Phase 7)")
    parser.add_argument("--confirm-open-test-set", action="store_true")
    args = parser.parse_args()
    result = open_test_set_once(args.confirm_open_test_set)
    print(json.dumps({k: {"model1": v["model1"], "baseline_3": v["baseline_3"], "ratio": v["rmse_ratio_vs_baseline_3"],
                          "coverage": v["interval_coverage"]} for k, v in result["groups"].items()}, indent=2))
