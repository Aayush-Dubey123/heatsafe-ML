import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from ml.src.commons.logger import get_ml_logger

logging = get_ml_logger(__name__)


class DataManifestManager:
    """
    Manages the cryptographic hashing, validation, and registration
    of geospatial data assets into the tracked project data manifest.
    """

    def __init__(self, manifest_path: Optional[Path] = None):
        """
        Initialize the DataManifestManager with an absolute manifest filepath.

        Args:
            manifest_path (Optional[Path]): Destination JSON manifest path.
                Defaults to ml/data/manifest/data_manifest.json.
        """
        if manifest_path is None:
            self.manifest_path = Path(__file__).resolve().parent.parent.parent / "data" / "manifest" / "data_manifest.json"
        else:
            self.manifest_path = manifest_path

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """
        Compute SHA-256 digest of an on-disk binary or text file.

        Args:
            file_path (Path): Path of file to hash.

        Returns:
            str: Hexadecimal SHA-256 string.

        Raises:
            FileNotFoundError: If the target file does not exist.
        """
        if not file_path.is_file():
            logging.error(f"Cannot compute hash: file not found at {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def record_entry(
        self,
        source: str,
        scene_id: str,
        acquisition_date: str,
        file_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a new verified data asset into the manifest with cryptographic proof.

        Args:
            source (str): Data provider (e.g. 'USGS_Landsat_8_C2L2', 'Sentinel-2').
            scene_id (str): Unique provider scene identifier.
            acquisition_date (str): ISO 8601 acquisition timestamp string.
            file_path (Path): Path to the verified local file.
            metadata (Optional[Dict[str, Any]]): Additional properties (e.g. cloud_cover).

        Returns:
            Dict[str, Any]: Constructed manifest record object.

        Raises:
            FileNotFoundError: If file_path does not exist.
        """
        logging.info(f"Executing DataManifestManager.record_entry for scene {scene_id}")
        file_hash = self.compute_sha256(file_path)
        file_size = file_path.stat().st_size

        entry = {
            "source": source,
            "scene_id": scene_id,
            "acquisition_date": acquisition_date,
            "sha256": file_hash,
            "size_bytes": file_size,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        records = self.load_all_records()
        # Deduplicate by scene_id
        records = [r for r in records if r.get("scene_id") != scene_id]
        records.append(entry)

        self._save_records(records)
        logging.info(f"Scene {scene_id} registered in manifest successfully")
        return entry

    def load_all_records(self) -> List[Dict[str, Any]]:
        """
        Load all registered data asset records from the persistent manifest file.

        Returns:
            List[Dict[str, Any]]: List of recorded data entries.

        Raises:
            None
        """
        if not self.manifest_path.is_file():
            return []
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as err:
            logging.error(f"Failed to read manifest at {self.manifest_path}: {err}")
            return []

    def _save_records(self, records: List[Dict[str, Any]]) -> None:
        """
        Atomically persist asset entries list to the manifest destination.

        Args:
            records (List[Dict[str, Any]]): Complete list of records.

        Returns:
            None
        """
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
