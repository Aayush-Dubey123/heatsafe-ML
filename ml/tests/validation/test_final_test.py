import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.src.validation import final_test


def test_test_set_requires_explicit_confirmation():
    """
    The test set cannot be opened by accident.
    """
    with pytest.raises(PermissionError, match="confirm"):
        final_test.open_test_set_once(confirm=False)


def test_test_set_cannot_be_reopened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Once the lock file exists, a second opening is refused (Decision D4).
    """
    lock = tmp_path / "test_set_opened.json"
    lock.write_text(json.dumps({"opened_utc": "2026-11-09T00:00:00+00:00", "model": "m1-x"}))
    monkeypatch.setattr(final_test, "LOCK_FILE", lock)
    with pytest.raises(PermissionError, match="already opened"):
        final_test.open_test_set_once(confirm=True)


def test_block_bootstrap_ci_brackets_point_estimate():
    """
    Block-bootstrap intervals contain the full-sample RMSE and are ordered.
    """
    rng = np.random.default_rng(0)
    frame = pd.DataFrame({
        "block_id": np.repeat([f"B{i}" for i in range(40)], 50),
        "lst_celsius": rng.normal(40, 3, 2000),
    })
    frame["pred"] = frame["lst_celsius"] + rng.normal(0, 1.5, 2000)
    ci = final_test.block_bootstrap_ci(frame, "pred", n_resamples=300, seed=1)
    rmse = float(np.sqrt(np.mean((frame["pred"] - frame["lst_celsius"]) ** 2)))
    assert ci["rmse"][0] <= rmse <= ci["rmse"][1]
    assert ci["bias"][0] < ci["bias"][1]


def test_land_cover_proxy_classes():
    """
    NDVI/NDBI thresholds map to the three coarse classes.
    """
    frame = pd.DataFrame({"ndvi": [0.6, 0.1, 0.2], "ndbi": [-0.2, 0.1, -0.1]})
    assert final_test.land_cover_class(frame).tolist() == ["vegetation", "built_up", "bare_or_mixed"]
