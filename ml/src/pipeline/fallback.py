"""
HeatSafe-ML pipeline safety helpers (Phase 10): run lock, stale-product fallback, run audit.

When a run fails (network outage, corrupt raster, database down) or finds no new
scene, the last good product stays published and is flagged `stale` once it is
older than the freshness limit (Decision D2). Nothing is ever half-published.
"""

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from ml.src.commons.logger import get_ml_logger
from ml.src.publish.products import freshness, read_latest, set_latest

logging = get_ml_logger(__name__)


class RunLockError(RuntimeError):
    """
    Raised when another pipeline run already holds the lock.
    """


class RunLock:
    """
    File lock preventing overlapping pipeline runs.

    The lock file is created exclusively; a lock older than `timeout_hours` is
    treated as left behind by a crashed run and is replaced.
    """

    def __init__(self, path: Path, timeout_hours: float, now: datetime | None = None) -> None:
        """
        Configure the lock.

        Args:
            path (Path): Lock file location.
            timeout_hours (float): Age after which an existing lock is considered abandoned.
            now (datetime | None): Clock override for tests.
        """
        self.path = Path(path)
        self.timeout_hours = float(timeout_hours)
        self.now = now

    def __enter__(self) -> "RunLock":
        """
        Acquire the lock.

        Returns:
            RunLock: This lock.

        Raises:
            RunLockError: If a fresh lock is already held.
        """
        current = self.now or datetime.now(UTC)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_file():
            try:
                started = datetime.fromisoformat(json.loads(self.path.read_text(encoding="utf-8"))["started_utc"])
                age_hours = (current - started).total_seconds() / 3600.0
            except (ValueError, KeyError, json.JSONDecodeError):
                age_hours = float("inf")
            if age_hours < self.timeout_hours:
                raise RunLockError(f"Another pipeline run holds the lock (started {age_hours:.1f} h ago)")
            logging.warning(f"Replacing abandoned pipeline lock ({age_hours:.1f} h old)")
            self.path.unlink()
        handle = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump({"started_utc": current.isoformat(), "pid": os.getpid()}, stream)
        return self

    def __exit__(self, *exc_info: object) -> None:
        """
        Release the lock.

        Args:
            *exc_info (object): Exception details (ignored; the lock is always released).
        """
        self.path.unlink(missing_ok=True)


def serve_last_good(root: Path, reason: str, today: date, max_age_days: int) -> dict[str, Any]:
    """
    Keep the last good product published, refresh its age, and record why no new one replaced it.

    Args:
        root (Path): Published root folder.
        reason (str): Short machine-readable cause, e.g. "network_error".
        today (date): Reference date.
        max_age_days (int): Staleness limit in days.

    Returns:
        dict[str, Any]: The updated pointer, or {"version": None, "stale": True, ...} if nothing was ever published.
    """
    pointer = read_latest(root)
    if pointer is None:
        logging.warning(f"Fallback requested ({reason}) but no product has been published yet")
        return {"version": None, "stale": True, "scene_age_days": None, "last_run_issue": reason}
    pointer.update(freshness(str(pointer["scene_date"]), today, max_age_days))
    pointer["last_run_issue"] = reason
    pointer["last_checked_utc"] = datetime.now(UTC).isoformat()
    set_latest(root, pointer)
    logging.warning(f"Serving last good product {pointer['version']} (reason={reason}, stale={pointer['stale']})")
    return pointer


def record_run(database_url: str | None, run: dict[str, Any]) -> bool:
    """
    Append one row to `pipeline_runs`; never raises.

    A database outage must not turn a successful publish into a failed run, so
    errors are logged and reported through the return value.

    Args:
        database_url (str | None): Serving database URL; None skips recording.
        run (dict[str, Any]): started_at, finished_at, status, scene_id, product_version, detail.

    Returns:
        bool: True if the row was written.
    """
    if not database_url:
        return False
    try:
        from sqlalchemy import MetaData, Table, create_engine, insert

        connect_args = {} if database_url.startswith("sqlite") else {"connect_timeout": 10}
        engine = create_engine(database_url, connect_args=connect_args)
        with engine.begin() as connection:
            table = Table("pipeline_runs", MetaData(), autoload_with=connection)
            connection.execute(insert(table), [run])
        engine.dispose()
        return True
    except Exception as error:
        logging.error(f"Error in record_run: {type(error).__name__}: {error}")
        return False
