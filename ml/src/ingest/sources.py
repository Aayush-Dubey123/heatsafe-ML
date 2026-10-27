import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from ml.src.commons.logger import get_ml_logger
from ml.src.commons.manifest import DataManifestManager

logging = get_ml_logger(__name__)


class STACIngestionClient:
    """
    Client for querying open satellite STAC APIs and downloading Cloud-Optimized
    GeoTIFF assets with exponential backoff and cryptographic manifest tracking.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the STAC ingestion client with configuration settings.

        Args:
            config_path (Optional[Path]): Path to ingest.yaml configuration file.

        Returns:
            None.

        Raises:
            FileNotFoundError: If the specified configuration file does not exist.
        """
        logging.info("Executing STACIngestionClient.__init__")
        if config_path is None:
            self.config_path = (
                Path(__file__).resolve().parent.parent.parent / "configs" / "ingest.yaml"
            )
        else:
            self.config_path = config_path

        if not self.config_path.is_file():
            logging.error(f"Configuration file not found: {self.config_path}")
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.search_endpoint = self.config["stac_service"]["search_endpoint"]
        self.signing_endpoint = self.config["stac_service"]["signing_endpoint"]
        self.retry_policy = self.config.get("retry_policy", {})
        self.max_retries = int(self.retry_policy.get("max_retries", 5))
        self.initial_delay = float(self.retry_policy.get("initial_delay_seconds", 1.0))
        self.backoff_factor = float(self.retry_policy.get("backoff_factor", 2.0))

    def search_landsat_scenes(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_cloud: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query Planetary Computer STAC for Landsat 8 and 9 Collection 2 Level-2 scenes.

        Args:
            start_date (Optional[str]): Start of acquisition window (ISO 8601).
            end_date (Optional[str]): End of acquisition window (ISO 8601).
            max_cloud (Optional[float]): Maximum permitted cloud cover percentage.
            limit (Optional[int]): Maximum number of scenes to return.

        Returns:
            List[Dict[str, Any]]: List of matching STAC feature dictionaries.

        Raises:
            RuntimeError: If the STAC search query fails or returns non-200.
        """
        logging.info("Executing STACIngestionClient.search_landsat_scenes")
        spatial = self.config["spatial_constraints"]
        bbox = [
            spatial["bounding_box"]["min_longitude"],
            spatial["bounding_box"]["min_latitude"],
            spatial["bounding_box"]["max_longitude"],
            spatial["bounding_box"]["max_latitude"],
        ]
        start = start_date or self.config["temporal_constraints"]["training_start_date"]
        end = end_date or self.config["temporal_constraints"]["training_end_date"]
        cloud = max_cloud if max_cloud is not None else float(self.config["filtering"]["cloud_cover_max"])

        payload: Dict[str, Any] = {
            "collections": [self.config["sources"]["landsat"]["stac_collection"]],
            "bbox": bbox,
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
            "query": {
                "eo:cloud_cover": {"lt": cloud},
                "landsat:wrs_path": {"eq": str(spatial["wrs_path"])},
                "landsat:wrs_row": {"eq": str(spatial["wrs_row"])},
            },
            "limit": min(limit, 250) if limit else 250,
            "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        }

        features: List[Dict[str, Any]] = []
        next_url: Optional[str] = self.search_endpoint
        post_body: Optional[bytes] = json.dumps(payload).encode("utf-8")

        while next_url:
            req = urllib.request.Request(
                next_url,
                data=post_body,
                headers={"Content-Type": "application/json", "User-Agent": "HeatSafeML/1.0"},
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                logging.error(f"Error querying STAC endpoint {next_url}: {e}")
                raise RuntimeError(f"STAC query failed: {e}")

            batch = data.get("features", [])
            features.extend(batch)
            logging.info(f"Retrieved {len(batch)} Landsat scenes (accumulated {len(features)})")

            if limit and len(features) >= limit:
                features = features[:limit]
                break

            # Check next link for pagination
            next_link = next((lk for lk in data.get("links", []) if lk.get("rel") == "next"), None)
            if next_link and next_link.get("href"):
                next_url = next_link["href"]
                # If next link is GET, data should be None; if POST, keep body
                if next_link.get("method", "GET").upper() == "GET":
                    post_body = None
            else:
                next_url = None

        return features

    def search_sentinel2_scenes(
        self,
        target_datetime: str,
        window_days: Optional[int] = None,
        max_cloud: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query STAC for Sentinel-2 L2A scenes matching a target Landsat acquisition time.

        Args:
            target_datetime (str): ISO 8601 acquisition timestamp of reference scene.
            window_days (Optional[int]): Number of days before and after target timestamp.
            max_cloud (Optional[float]): Maximum cloud cover threshold.
            limit (Optional[int]): Maximum number of scenes to return.

        Returns:
            List[Dict[str, Any]]: List of matching Sentinel-2 STAC features.

        Raises:
            RuntimeError: If query parameters are invalid or STAC request fails.
        """
        logging.info(f"Executing STACIngestionClient.search_sentinel2_scenes around {target_datetime}")
        spatial = self.config["spatial_constraints"]
        bbox = [
            spatial["bounding_box"]["min_longitude"],
            spatial["bounding_box"]["min_latitude"],
            spatial["bounding_box"]["max_longitude"],
            spatial["bounding_box"]["max_latitude"],
        ]
        days = window_days or int(self.config["sources"]["sentinel2"]["match_window_days"])
        cloud = max_cloud if max_cloud is not None else float(self.config["filtering"]["cloud_cover_max"])

        dt = datetime.fromisoformat(target_datetime.replace("Z", "+00:00"))
        start_str = (dt - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = (dt + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload: Dict[str, Any] = {
            "collections": [self.config["sources"]["sentinel2"]["stac_collection"]],
            "bbox": bbox,
            "datetime": f"{start_str}/{end_str}",
            "query": {
                "eo:cloud_cover": {"lt": cloud},
            },
            "limit": limit or 10,
            "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        }

        req = urllib.request.Request(
            self.search_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "HeatSafeML/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logging.error(f"Error searching Sentinel-2 scenes: {e}")
            raise RuntimeError(f"Sentinel-2 search failed: {e}")

        return data.get("features", [])

    def search_copernicus_dem_tiles(
        self,
        bbox: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query STAC for Copernicus DEM GLO-30 static elevation tiles over the study area.

        Args:
            bbox (Optional[List[float]]): Geographic bounding box [min_x, min_y, max_x, max_y].

        Returns:
            List[Dict[str, Any]]: Matching Copernicus DEM tile features.

        Raises:
            RuntimeError: If STAC query fails.
        """
        logging.info("Executing STACIngestionClient.search_copernicus_dem_tiles")
        if bbox is None:
            spatial = self.config["spatial_constraints"]
            bbox = [
                spatial["bounding_box"]["min_longitude"],
                spatial["bounding_box"]["min_latitude"],
                spatial["bounding_box"]["max_longitude"],
                spatial["bounding_box"]["max_latitude"],
            ]

        payload: Dict[str, Any] = {
            "collections": [self.config["sources"]["dem"]["stac_collection"]],
            "bbox": bbox,
            "limit": 10,
        }

        req = urllib.request.Request(
            self.search_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "HeatSafeML/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logging.error(f"Error querying Copernicus DEM tiles: {e}")
            raise RuntimeError(f"DEM query failed: {e}")

        return data.get("features", [])

    def sign_asset_url(self, href: str) -> str:
        """
        Sign a Planetary Computer storage asset URL via the public SAS token service.

        Args:
            href (str): Raw asset href from STAC metadata.

        Returns:
            str: Authenticated URL containing valid SAS access token.

        Raises:
            RuntimeError: If SAS signing endpoint is unreachable or fails.
        """
        logging.info(f"Signing asset URL: {href[:60]}...")
        sign_url = f"{self.signing_endpoint}?href={urllib.parse.quote(href)}"
        req = urllib.request.Request(sign_url, headers={"User-Agent": "HeatSafeML/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["href"]
        except Exception as e:
            logging.error(f"Error obtaining signed asset URL for {href[:60]}: {e}")
            raise RuntimeError(f"SAS signing failed: {e}")

    def download_asset_with_retry(
        self,
        url: str,
        destination: Path,
        max_retries: Optional[int] = None,
        initial_delay: Optional[float] = None,
        backoff_factor: Optional[float] = None,
    ) -> Path:
        """
        Download a remote raster asset using streaming chunked I/O with exponential backoff.

        Args:
            url (str): Remote asset download URL (signed SAS URL).
            destination (Path): Target local file path for storage.
            max_retries (Optional[int]): Maximum number of retry attempts.
            initial_delay (Optional[float]): Base backoff delay in seconds.
            backoff_factor (Optional[float]): Multiplicative factor per retry.

        Returns:
            Path: Path to the successfully downloaded file on disk.

        Raises:
            RuntimeError: If download fails after all retry attempts are exhausted.
        """
        retries = max_retries if max_retries is not None else self.max_retries
        delay = initial_delay if initial_delay is not None else self.initial_delay
        factor = backoff_factor if backoff_factor is not None else self.backoff_factor

        destination.parent.mkdir(parents=True, exist_ok=True)
        attempt = 0

        while attempt <= retries:
            try:
                logging.info(f"Downloading {destination.name} (attempt {attempt + 1}/{retries + 1})")
                req = urllib.request.Request(url, headers={"User-Agent": "HeatSafeML/1.0"})
                with urllib.request.urlopen(req, timeout=60) as resp, open(destination, "wb") as f_out:
                    while chunk := resp.read(65536):
                        f_out.write(chunk)

                if destination.stat().st_size == 0:
                    raise IOError("Downloaded file has 0 bytes")

                logging.info(f"Successfully downloaded {destination.name} ({destination.stat().st_size} bytes)")
                return destination

            except Exception as e:
                attempt += 1
                logging.warning(f"Download failure for {destination.name} on attempt {attempt}: {e}")
                # Clean up partial artifacts
                if destination.is_file():
                    destination.unlink(missing_ok=True)

                if attempt > retries:
                    logging.error(f"All {retries} retry attempts exhausted for {destination.name}")
                    raise RuntimeError(f"Failed to download asset after {retries} retries: {e}")

                sleep_time = delay * (factor ** (attempt - 1))
                logging.info(f"Backing off for {sleep_time:.2f}s before retry...")
                time.sleep(sleep_time)

        raise RuntimeError(f"Download loop terminated unexpectedly for {destination}")

    @staticmethod
    def is_scene_ingested(
        scene_id: str,
        manifest_manager: DataManifestManager,
    ) -> bool:
        """
        Check whether a scene is already cryptographically registered in the manifest.

        Args:
            scene_id (str): Unique scene identifier.
            manifest_manager (DataManifestManager): Active manifest manager instance.

        Returns:
            bool: True if scene is registered with verified SHA256 on disk, False otherwise.
        """
        records = manifest_manager.load_all_records()
        record = next((r for r in records if r.get("scene_id") == scene_id), None)
        return record is not None
