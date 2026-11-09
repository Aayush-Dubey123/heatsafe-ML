from pathlib import Path

import numpy as np
import pytest

from ml.src.dataset.build import discover_scenes, scene_seed
from ml.src.dataset.splits import assign_split_columns, generate_splits, grid_block_ids


def test_grid_has_180_blocks_matching_feature_table_scheme():
    """
    The 28.26 km x 23.85 km grid is covered by 15 x 12 = 180 two-kilometre blocks (D5).
    """
    blocks = grid_block_ids(2000.0)
    assert len(blocks) == 180
    assert blocks[0] == "B_00_00" and blocks[-1] == "B_14_11"


def test_splits_are_deterministic_disjoint_and_complete():
    """
    Holdout and CV blocks never overlap, cover every block, and are reproducible.
    """
    blocks = grid_block_ids(2000.0)
    first = generate_splits(blocks, holdout_fraction=0.2, n_folds=5, seed=7)
    second = generate_splits(blocks, holdout_fraction=0.2, n_folds=5, seed=7)
    assert first == second

    holdout = set(first["holdout_blocks"])
    cv_blocks = set(first["fold_of_block"])
    assert len(holdout) == 36
    assert holdout.isdisjoint(cv_blocks)
    assert holdout | cv_blocks == set(blocks)

    fold_sizes = np.bincount(list(first["fold_of_block"].values()))
    assert len(fold_sizes) == 5 and fold_sizes.max() - fold_sizes.min() <= 1


def test_different_seed_changes_holdout():
    """
    The seed actually drives the holdout choice.
    """
    blocks = grid_block_ids(2000.0)
    a = generate_splits(blocks, 0.2, 5, seed=1)["holdout_blocks"]
    b = generate_splits(blocks, 0.2, 5, seed=2)["holdout_blocks"]
    assert a != b


@pytest.mark.parametrize("fraction,folds", [(0.0, 5), (1.0, 5), (0.2, 1)])
def test_invalid_split_parameters_rejected(fraction, folds):
    """
    Degenerate split settings are refused.
    """
    with pytest.raises(ValueError):
        generate_splits(["B_00_00", "B_00_01"], fraction, folds, seed=0)


def test_assign_split_columns_marks_holdout_with_fold_minus_one():
    """
    Holdout rows get fold -1; CV rows get their block's fold.
    """
    splits = {"holdout_blocks": ["B_00_00"], "fold_of_block": {"B_00_01": 3, "B_01_00": 0}}
    is_holdout, fold = assign_split_columns(np.array(["B_00_00", "B_00_01", "B_01_00"]), splits)
    assert is_holdout.tolist() == [True, False, False]
    assert fold.tolist() == [-1, 3, 0]


def test_scene_seed_is_stable():
    """
    Per-scene sampling seeds are deterministic and scene-specific.
    """
    assert scene_seed("LC08_L2SP_144045_20240529_02_T1", 5) == scene_seed("LC08_L2SP_144045_20240529_02_T1", 5)
    assert scene_seed("LC08_L2SP_144045_20240529_02_T1", 5) != scene_seed("LC09_L2SP_144045_20240529_02_T1", 5)


def test_discover_scenes_requires_all_core_bands(tmp_path: Path):
    """
    Complete scenes are discovered with dates; scenes missing a band are skipped.
    """
    complete = "LC08_L2SP_144045_20240529_02_T1"
    partial = "LC09_L2SP_144045_20240606_02_T1"
    for band in ("ST_B10", "QA_PIXEL", "QA_RADSAT", "SR_B3", "SR_B4", "SR_B5", "SR_B6"):
        (tmp_path / f"{complete}_{band}.tif").write_bytes(b"x")
    for band in ("ST_B10", "QA_PIXEL"):
        (tmp_path / f"{partial}_{band}.tif").write_bytes(b"x")

    scenes = discover_scenes(tmp_path)
    assert [s["scene_id"] for s in scenes] == [complete]
    assert scenes[0]["date"] == "2024-05-29"
    assert scenes[0]["acquisition_datetime"].startswith("2024-05-29T")


def test_focal_mean_ignores_invalid_cells():
    """
    Neighbourhood means skip NaN and out-of-range index values.
    """
    from ml.src.dataset.build import focal_mean

    grid = np.full((7, 7), 0.5, dtype=np.float32)
    grid[3, 3] = 8.0          # out of [-1, 1]: ignored
    grid[0, 0] = np.nan       # missing: ignored
    result = focal_mean(grid, 3)
    assert result[3, 3] == pytest.approx(0.5)
    assert result[1, 1] == pytest.approx(0.5)
