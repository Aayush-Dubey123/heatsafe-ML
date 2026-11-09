"""
HeatSafe-ML spatial split definitions (Decisions D4 and D5).

Every 2 km block of the master grid is assigned exactly once to either the fixed
held-out test set (opened once, in Phase 7) or one of the cross-validation folds.
The assignment is deterministic and frozen in `ml/configs/splits.yaml`.
"""

from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ml.src.commons.logger import get_ml_logger
from ml.src.preprocess.align import load_master_grid_spec

logging = get_ml_logger(__name__)

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"
SPLITS_PATH = CONFIG_DIR / "splits.yaml"
THRESHOLDS_PATH = CONFIG_DIR / "thresholds.yaml"


def load_thresholds() -> dict[str, Any]:
    """
    Load the scientific thresholds configuration.

    Returns:
        dict[str, Any]: Parsed `ml/configs/thresholds.yaml`.
    """
    with open(THRESHOLDS_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def grid_block_ids(block_size: float = 2000.0) -> list[str]:
    """
    List every 2 km block id that intersects the master grid.

    Uses the same `B_cc_rr` origin-anchored scheme as the feature table (D5).

    Args:
        block_size (float): Block edge length in metres.

    Returns:
        list[str]: Sorted block identifiers.
    """
    spec = load_master_grid_spec()
    width = spec["max_easting"] - spec["min_easting"]
    height = spec["max_northing"] - spec["min_northing"]
    n_cols = int(np.ceil(width / block_size))
    n_rows = int(np.ceil(height / block_size))
    return sorted(f"B_{c:02d}_{r:02d}" for c in range(n_cols) for r in range(n_rows))


def generate_splits(
    block_ids: list[str],
    holdout_fraction: float,
    n_folds: int,
    seed: int,
) -> dict[str, Any]:
    """
    Deterministically split blocks into fixed test blocks and CV folds.

    A seeded permutation picks `holdout_fraction` of blocks for the test set;
    the remaining blocks are dealt round-robin into `n_folds` folds.

    Args:
        block_ids (list[str]): All block identifiers.
        holdout_fraction (float): Share of blocks reserved for the final test.
        n_folds (int): Number of cross-validation folds.
        seed (int): Random seed.

    Returns:
        dict[str, Any]: {"holdout_blocks": [...], "fold_of_block": {block: fold}, ...}.

    Raises:
        ValueError: If the fraction or fold count is invalid.
    """
    if not 0.0 < holdout_fraction < 1.0:
        raise ValueError("holdout_fraction must be between 0 and 1")
    if n_folds < 2:
        raise ValueError("n_folds must be at least 2")

    ordered = sorted(block_ids)
    rng = np.random.default_rng(seed)
    permuted = [ordered[i] for i in rng.permutation(len(ordered))]
    n_holdout = int(round(holdout_fraction * len(ordered)))
    holdout = sorted(permuted[:n_holdout])
    remaining = permuted[n_holdout:]
    fold_of_block = {block: idx % n_folds for idx, block in enumerate(remaining)}
    return {
        "seed": seed,
        "n_folds": n_folds,
        "holdout_fraction": holdout_fraction,
        "holdout_blocks": holdout,
        "fold_of_block": dict(sorted(fold_of_block.items())),
    }


def load_or_create_splits() -> dict[str, Any]:
    """
    Load the frozen split file, creating it from config on first use.

    Once written, `splits.yaml` is the source of truth and is never regenerated
    automatically, so the test blocks cannot drift between runs.

    Returns:
        dict[str, Any]: Split definition (see `generate_splits`).
    """
    if SPLITS_PATH.is_file():
        with open(SPLITS_PATH, encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    cfg = load_thresholds()["spatial_splits"]
    splits = generate_splits(
        grid_block_ids(cfg["block_size_meters"]),
        holdout_fraction=float(cfg["holdout_fraction"]),
        n_folds=int(cfg["n_folds"]),
        seed=int(cfg["random_seed"]),
    )
    header = (
        "# HeatSafe-ML frozen spatial splits (Decisions D4/D5). Generated once by\n"
        "# ml/src/dataset/splits.py — do not edit by hand. Holdout blocks are the\n"
        "# final test set and must not be used before Phase 7.\n"
    )
    with open(SPLITS_PATH, "w", encoding="utf-8") as handle:
        handle.write(header)
        yaml.safe_dump(splits, handle, sort_keys=False)
    logging.info(
        f"Created {SPLITS_PATH.name}: {len(splits['holdout_blocks'])} holdout blocks, "
        f"{len(splits['fold_of_block'])} CV blocks in {splits['n_folds']} folds"
    )
    return splits


def assign_split_columns(block_ids: np.ndarray, splits: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """
    Map block ids to holdout flags and CV fold numbers.

    Args:
        block_ids (np.ndarray): Block id per row.
        splits (dict[str, Any]): Split definition.

    Returns:
        tuple[np.ndarray, np.ndarray]: (is_holdout bool array, fold int8 array; -1 for holdout rows).
    """
    holdout = set(splits["holdout_blocks"])
    fold_map = splits["fold_of_block"]
    is_holdout = np.array([b in holdout for b in block_ids], dtype=bool)
    fold = np.array([-1 if b in holdout else fold_map[b] for b in block_ids], dtype=np.int8)
    return is_holdout, fold
