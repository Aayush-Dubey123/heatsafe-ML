"""
HeatSafe-ML Model 1 evaluation and registration (Phase 6).

Runs tuning, 5-fold spatial-block CV, the Random Forest comparison, interval
coverage, and SHAP; checks the Phase 6 gate against Baseline 3; logs the run to
JSON; and saves the final models to the git-ignored registry with SHA-256 hashes.

Usage:
    python -m ml.src.models.core.evaluate
"""

import hashlib
import json
import subprocess  # noqa: S404 - only used to read the local git commit
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.src.commons.logger import get_ml_logger
from ml.src.commons.manifest import DataManifestManager
from ml.src.dataset.build import PROCESSED_DIR, TRAINING_TABLE
from ml.src.dataset.splits import load_thresholds
from ml.src.models.baseline.baselines import BASELINE_DIR, cv_eligible
from ml.src.models.baseline.metrics import metrics_by_group
from ml.src.models.core.train import (
    add_derived_features,
    attach_scene_anchor,
    cross_validate_model1,
    feature_names,
    fit_fold_models,
    fit_random_forest_comparison,
    load_model_config,
    tune_hyperparameters,
)
from ml.src.models.explain.intervals import coverage_by_group
from ml.src.models.explain.shap_analysis import plot_importance, shap_importance

logging = get_ml_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENTS_DIR = PROCESSED_DIR / "experiments"
REGISTRY_DIR = REPO_ROOT / "ml" / "models" / "registry"


def git_commit() -> str:
    """
    Return the current git commit hash, or "unknown" outside a repository.

    Returns:
        str: Commit SHA.
    """
    try:
        completed = subprocess.run(  # noqa: S603 - fixed command, no user input
            ["git", "rev-parse", "HEAD"],  # noqa: S607 - git is resolved from PATH
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=10,
        )
        return str(completed.stdout).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path) -> str:
    """
    Hash a file with SHA-256.

    Args:
        path (Path): File to hash.

    Returns:
        str: Hex digest.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def phase6_gate(model_rmse: float, baseline3_rmse: float, coverage: float, min_improvement: float,
                min_coverage: float) -> dict[str, Any]:
    """
    Evaluate the Phase 6 exit criteria.

    Args:
        model_rmse (float): Model 1 CV RMSE.
        baseline3_rmse (float): Baseline 3 CV RMSE.
        coverage (float): Empirical 90%-interval coverage (0–1).
        min_improvement (float): Required RMSE reduction (e.g. 0.15).
        min_coverage (float): Required coverage (e.g. 0.85).

    Returns:
        dict[str, Any]: improvement, flags, and overall pass.
    """
    improvement = 1.0 - model_rmse / baseline3_rmse
    beats = improvement >= min_improvement
    covers = coverage >= min_coverage
    return {
        "rmse_improvement_vs_baseline3": round(improvement, 4),
        "meets_rmse_criterion": bool(beats),
        "meets_coverage_criterion": bool(covers),
        "passed": bool(beats and covers),
    }


def run_phase6() -> dict[str, Any]:
    """
    Execute the full Phase 6 workflow and return the run record.

    Returns:
        dict[str, Any]: Experiment record (also written to processed/experiments/).

    Raises:
        FileNotFoundError: If Phase 5 baseline scores are missing.
    """
    cfg = load_model_config()
    thresholds = load_thresholds()
    baseline_file = BASELINE_DIR / "baseline_scores.json"
    if not baseline_file.is_file():
        raise FileNotFoundError("Run Phase 5 baselines first (baseline_scores.json missing)")
    baselines = json.loads(baseline_file.read_text(encoding="utf-8"))

    table = add_derived_features(cv_eligible(pd.read_parquet(TRAINING_TABLE)))
    best_params, trials = tune_hyperparameters(table, cfg)
    oof = cross_validate_model1(table, cfg, best_params, with_intervals=True)
    rf_oof = fit_random_forest_comparison(table, cfg)

    scores = {
        "model1_lgbm": metrics_by_group(oof, "lst_celsius", "pred_lgbm"),
        "model1_lgbm_rk": metrics_by_group(oof, "lst_celsius", "pred_rk"),
        "random_forest": metrics_by_group(rf_oof, "lst_celsius", "pred_rf"),
    }
    use_rk = scores["model1_lgbm_rk"]["overall"]["rmse"] < scores["model1_lgbm"]["overall"]["rmse"]
    chosen = "model1_lgbm_rk" if use_rk else "model1_lgbm"
    coverage = coverage_by_group(oof, "lower_rk" if use_rk else "lower", "upper_rk" if use_rk else "upper")

    gate = phase6_gate(
        scores[chosen]["overall"]["rmse"], baselines["baseline_3"]["overall"]["rmse"],
        coverage["overall"]["coverage"],
        float(thresholds["model_baselines"]["min_rmse_improvement_percent"]) / 100.0, 0.85,
    )

    # Final models: refit on every CV-eligible row with the tuned parameters.
    final_train = table.copy()
    final_train["scene_anchor_lst"] = attach_scene_anchor(final_train, final_train)
    models = fit_fold_models(final_train, cfg, best_params, with_intervals=True)
    features = feature_names(cfg)
    explain_sample = final_train.sample(n=min(50000, len(final_train)), random_state=int(cfg["random_seed"]))
    importance = shap_importance(models["point"], explain_sample, features)

    version = datetime.now(UTC).strftime("m1-%Y%m%dT%H%M%SZ")
    model_dir = REGISTRY_DIR / version
    model_dir.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, model in models.items():
        path = model_dir / f"{name}.txt"
        model.booster_.save_model(str(path))
        hashes[path.name] = sha256_file(path)

    record = {
        "model_version": version,
        "created_utc": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(),
        "data": {"training_table": str(TRAINING_TABLE.name), "sha256": sha256_file(TRAINING_TABLE),
                 "cv_rows": int(len(table)), "scenes": int(table["scene_id"].nunique())},
        "features": features,
        "tuned_params": best_params,
        "tuning_trials": trials,
        "chosen_variant": chosen,
        "residual_kriging": bool(use_rk),
        "cv_scores": scores,
        "baseline_3": baselines["baseline_3"],
        "interval_coverage": coverage,
        "shap_importance": importance,
        "phase6_gate": gate,
        "model_files": hashes,
    }
    (model_dir / "metadata.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = EXPERIMENTS_DIR / f"{version}.json"
    run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    oof.to_parquet(EXPERIMENTS_DIR / f"{version}_oof.parquet", index=False)
    plot_importance(importance, EXPERIMENTS_DIR / f"{version}_shap.png")

    manifest = DataManifestManager()
    for name, digest in hashes.items():
        manifest.record_entry(source="heatsafe_model1", scene_id=f"{version}/{name}",
                              acquisition_date=record["created_utc"], file_path=model_dir / name,
                              metadata={"model_version": version, "sha256": digest})
    logging.info(f"Phase 6 gate: {gate}")
    return record


def summary_table(record: dict[str, Any]) -> pd.DataFrame:
    """
    Compact per-season RMSE table for Model 1, Random Forest, and Baseline 3.

    Args:
        record (dict[str, Any]): Output of `run_phase6`.

    Returns:
        pd.DataFrame: RMSE by season (rows) and model (columns).
    """
    columns = {
        "baseline_3": record["baseline_3"],
        "random_forest": record["cv_scores"]["random_forest"],
        "model1_lgbm": record["cv_scores"]["model1_lgbm"],
        "model1_lgbm_rk": record["cv_scores"]["model1_lgbm_rk"],
    }
    seasons = list(columns["baseline_3"].keys())
    return pd.DataFrame({
        name: [round(scores.get(s, {}).get("rmse", np.nan), 3) for s in seasons] for name, scores in columns.items()
    }, index=seasons)


if __name__ == "__main__":
    result = run_phase6()
    print(summary_table(result).to_string())
    print(json.dumps({"gate": result["phase6_gate"], "coverage": result["interval_coverage"]["overall"]}, indent=2))
