"""
HeatSafe-ML exploratory statistics (Phase 5): Spearman correlations of LST with drivers.

Uses training-window, non-holdout rows of `training_v2.parquet` only.

Usage:
    python -m ml.src.eda.stats
"""

import json
from typing import Any

import pandas as pd
from scipy.stats import spearmanr

from ml.src.commons.logger import get_ml_logger
from ml.src.dataset.build import PROCESSED_DIR, TRAINING_TABLE
from ml.src.dataset.splits import load_thresholds

logging = get_ml_logger(__name__)

DRIVERS = ("ndvi", "ndbi", "mndwi", "elevation")


def spearman_by_season(table: pd.DataFrame, sample_per_season: int, seed: int) -> pd.DataFrame:
    """
    Compute Spearman rank correlation between LST and each driver, per season.

    Rows are subsampled per season for tractability; p-values are reported but,
    with spatially autocorrelated pixels, are optimistic and should be read with care.

    Args:
        table (pd.DataFrame): Training table rows.
        sample_per_season (int): Maximum rows used per season.
        seed (int): Sampling seed.

    Returns:
        pd.DataFrame: Columns season, driver, rho, p_value, n.
    """
    records: list[dict[str, Any]] = []
    for season, group in table.groupby("season"):
        sample = group.sample(n=min(sample_per_season, len(group)), random_state=seed)
        for driver in DRIVERS:
            rho, p_value = spearmanr(sample["lst_celsius"], sample[driver])
            records.append({
                "season": season, "driver": driver, "rho": round(float(rho), 3),
                "p_value": float(p_value), "n": int(len(sample)),
            })
    return pd.DataFrame(records)


def run_correlations() -> pd.DataFrame:
    """
    Load the training table, restrict to EDA-eligible rows, and save correlation results.

    Returns:
        pd.DataFrame: Correlation table (also written to processed/eda/spearman_by_season.json).
    """
    cfg = load_thresholds()
    table = pd.read_parquet(TRAINING_TABLE)
    eligible = table[(table["split"] == "train") & ~table["is_holdout_block"]]
    result = spearman_by_season(
        eligible, int(cfg["eda"]["correlation_sample_per_season"]), int(cfg["dataset"]["random_seed"])
    )
    out_dir = PROCESSED_DIR / "eda"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "spearman_by_season.json").write_text(result.to_json(orient="records", indent=2), encoding="utf-8")
    logging.info(f"Spearman correlations computed for {result['season'].nunique()} seasons")
    return result


if __name__ == "__main__":
    frame = run_correlations()
    print(frame.pivot(index="driver", columns="season", values="rho").to_string())
    print(json.dumps({"rows": len(frame)}))
