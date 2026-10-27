import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from ml.src.commons.logger import get_ml_logger
from ml.src.commons.manifest import DataManifestManager
from ml.src.ingest.sources import STACIngestionClient

logging = get_ml_logger(__name__)


def classify_season(month: int) -> str:
    """
    Classify calendar month into standard Indian Meteorological Department seasons.

    Args:
        month (int): Calendar month (1-12).

    Returns:
        str: Season label ('Winter', 'Summer', 'Monsoon', 'Post-Monsoon').

    Raises:
        ValueError: If month is outside the valid range 1-12.
    """
    if month in (12, 1, 2):
        return "Winter"
    elif month in (3, 4, 5):
        return "Summer"
    elif month in (6, 7, 8, 9):
        return "Monsoon"
    elif month in (10, 11):
        return "Post-Monsoon"
    raise ValueError(f"Invalid month: {month}")


def audit_seasonal_inventory(scenes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze retrieved scenes and compute distribution across seasons and years.

    Args:
        scenes (List[Dict[str, Any]]): List of STAC feature dictionaries.

    Returns:
        Dict[str, Any]: Audit summary containing counts per season and year, plus D7 evaluation.

    Raises:
        None.
    """
    logging.info(f"Executing audit_seasonal_inventory on {len(scenes)} scenes")
    seasons_count = {"Summer": 0, "Monsoon": 0, "Post-Monsoon": 0, "Winter": 0}
    by_year_season: Dict[int, Dict[str, int]] = {}

    for s in scenes:
        dt_str = s.get("properties", {}).get("datetime", "")
        if not dt_str:
            continue
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        season = classify_season(dt.month)
        seasons_count[season] += 1
        year_dict = by_year_season.setdefault(dt.year, {"Summer": 0, "Monsoon": 0, "Post-Monsoon": 0, "Winter": 0})
        year_dict[season] += 1

    total_scenes = len(scenes)
    # Decision D7: >= 40 usable scenes, >= 8 in each season
    meets_d7 = (
        total_scenes >= 40
        and all(c >= 8 for c in seasons_count.values())
    )

    return {
        "total_scenes": total_scenes,
        "seasons_count": seasons_count,
        "by_year_season": by_year_season,
        "meets_decision_d7": meets_d7,
    }


def run_landsat_ingestion(
    client: STACIngestionClient,
    manifest: DataManifestManager,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_cloud: Optional[float] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Execute Landsat Collection 2 Level-2 search and incremental asset download pipeline.

    Args:
        client (STACIngestionClient): Initialized STAC ingestion client.
        manifest (DataManifestManager): Initialized cryptographic manifest manager.
        start_date (Optional[str]): Start date for scene acquisition filter.
        end_date (Optional[str]): End date for scene acquisition filter.
        max_cloud (Optional[float]): Cloud cover percentage threshold.
        limit (Optional[int]): Cap on number of scenes to query or download.
        dry_run (bool): If True, queries catalog and audits inventory without downloading.

    Returns:
        Dict[str, Any]: Execution summary with scene counts, bytes downloaded, and status.

    Raises:
        RuntimeError: If remote queries or downloads encounter irrecoverable failures.
    """
    logging.info("Executing run_landsat_ingestion")
    scenes = client.search_landsat_scenes(
        start_date=start_date,
        end_date=end_date,
        max_cloud=max_cloud,
        limit=limit,
    )

    audit = audit_seasonal_inventory(scenes)
    logging.info(
        f"Inventory audit: Total={audit['total_scenes']}, "
        f"Summer={audit['seasons_count']['Summer']}, "
        f"Monsoon={audit['seasons_count']['Monsoon']}, "
        f"Post-Monsoon={audit['seasons_count']['Post-Monsoon']}, "
        f"Winter={audit['seasons_count']['Winter']}, "
        f"Meets D7={audit['meets_decision_d7']}"
    )

    if dry_run:
        logging.info("Dry-run requested: skipping file downloads and manifest registration.")
        return {
            "status": "dry_run_completed",
            "scenes_found": len(scenes),
            "audit": audit,
            "bytes_downloaded": 0,
            "scenes_downloaded": 0,
            "scenes_skipped": 0,
        }

    target_dir = Path(client.config["storage"]["landsat_dir"])
    target_bands = client.config["sources"]["landsat"]["target_bands"]
    downloaded_scenes = 0
    skipped_scenes = 0
    total_bytes = 0

    for scene in scenes:
        scene_id = scene["id"]
        # Idempotency check: skip already registered scenes
        if STACIngestionClient.is_scene_ingested(scene_id, manifest):
            logging.info(f"Scene {scene_id} already registered in manifest; skipping download (0 bytes)")
            skipped_scenes += 1
            continue

        logging.info(f"Ingesting new scene: {scene_id}")
        assets = scene.get("assets", {})
        band_paths: Dict[str, str] = {}
        primary_band_path: Optional[Path] = None

        for band_key, band_alias in target_bands.items():
            if band_key not in assets:
                logging.warning(f"Band {band_key} ({band_alias}) missing in assets for {scene_id}")
                continue

            raw_href = assets[band_key]["href"]
            signed_url = client.sign_asset_url(raw_href)
            dest_file = target_dir / f"{scene_id}_{band_alias}.tif"

            # Check if file exists on disk
            if dest_file.is_file() and dest_file.stat().st_size > 0:
                logging.info(f"Band file {dest_file.name} already exists on disk; skipping")
            else:
                downloaded_file = client.download_asset_with_retry(signed_url, dest_file)
                total_bytes += downloaded_file.stat().st_size

            band_paths[band_alias] = str(dest_file)
            if band_key == "lwir11":
                primary_band_path = dest_file

        if primary_band_path and primary_band_path.is_file():
            # Register in manifest
            manifest.record_entry(
                source="USGS_Landsat_C2L2",
                scene_id=scene_id,
                acquisition_date=scene.get("properties", {}).get("datetime", ""),
                file_path=primary_band_path,
                metadata={
                    "cloud_cover": scene.get("properties", {}).get("eo:cloud_cover"),
                    "platform": scene.get("properties", {}).get("platform"),
                    "wrs_path": scene.get("properties", {}).get("landsat:wrs_path"),
                    "wrs_row": scene.get("properties", {}).get("landsat:wrs_row"),
                    "bands": band_paths,
                },
            )
            downloaded_scenes += 1

    return {
        "status": "completed",
        "scenes_found": len(scenes),
        "audit": audit,
        "scenes_downloaded": downloaded_scenes,
        "scenes_skipped": skipped_scenes,
        "bytes_downloaded": total_bytes,
    }


def run_dem_ingestion(
    client: STACIngestionClient,
    manifest: DataManifestManager,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Execute Copernicus DEM GLO-30 static elevation tile ingestion pipeline.

    Args:
        client (STACIngestionClient): Initialized STAC ingestion client.
        manifest (DataManifestManager): Initialized cryptographic manifest manager.
        dry_run (bool): If True, queries catalog without downloading.

    Returns:
        Dict[str, Any]: Execution summary with tile counts and download status.

    Raises:
        RuntimeError: If STAC query or tile download fails.
    """
    logging.info("Executing run_dem_ingestion")
    tiles = client.search_copernicus_dem_tiles()
    logging.info(f"Found {len(tiles)} Copernicus DEM tiles")

    if dry_run:
        return {"status": "dry_run_completed", "tiles_found": len(tiles), "bytes_downloaded": 0}

    target_dir = Path(client.config["storage"]["dem_dir"])
    downloaded = 0
    total_bytes = 0

    for tile in tiles:
        tile_id = tile["id"]
        if STACIngestionClient.is_scene_ingested(tile_id, manifest):
            logging.info(f"DEM tile {tile_id} already registered in manifest; skipping")
            continue

        raw_href = tile.get("assets", {}).get("data", {}).get("href")
        if not raw_href:
            continue

        signed_url = client.sign_asset_url(raw_href)
        dest_file = target_dir / f"{tile_id}.tif"

        if not (dest_file.is_file() and dest_file.stat().st_size > 0):
            client.download_asset_with_retry(signed_url, dest_file)
            total_bytes += dest_file.stat().st_size

        manifest.record_entry(
            source="Copernicus_DEM_GLO30",
            scene_id=tile_id,
            acquisition_date="2020-01-01T00:00:00Z",
            file_path=dest_file,
            metadata={"type": "elevation_dsm", "resolution_meters": 30},
        )
        downloaded += 1

    return {
        "status": "completed",
        "tiles_found": len(tiles),
        "tiles_downloaded": downloaded,
        "bytes_downloaded": total_bytes,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    """
    Construct the command-line argument parser for the geospatial ingestion pipeline.

    Args:
        None.

    Returns:
        argparse.ArgumentParser: Configured argument parser instance.

    Raises:
        None.
    """
    parser = argparse.ArgumentParser(
        description="HeatSafe-ML — Incremental Satellite & Geospatial Data Ingestion CLI"
    )
    parser.add_argument(
        "--source",
        choices=["landsat", "sentinel2", "dem", "all"],
        default="landsat",
        help="Geospatial data source to ingest (default: landsat)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Acquisition start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Acquisition end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--max-cloud",
        type=float,
        default=None,
        help="Maximum cloud cover percentage (default from ingest.yaml: 20.0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of scenes to ingest",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Audit available catalog scenes without downloading rasters",
    )
    return parser


def main() -> None:
    """
    Main application entrypoint orchestrating CLI execution and reporting.

    Args:
        None.

    Returns:
        None.

    Raises:
        SystemExit: On execution completion or command argument errors.
    """
    parser = build_arg_parser()
    args = parser.parse_args()

    client = STACIngestionClient()
    manifest = DataManifestManager()

    logging.info(f"Initiating ingestion workflow: source={args.source}, dry_run={args.dry_run}")

    if args.source in ("landsat", "all"):
        res = run_landsat_ingestion(
            client=client,
            manifest=manifest,
            start_date=args.start_date,
            end_date=args.end_date,
            max_cloud=args.max_cloud,
            limit=args.limit,
            dry_run=args.dry_run,
        )
        print(f"Landsat Ingestion Result: {res}")

    if args.source in ("dem", "all"):
        res_dem = run_dem_ingestion(
            client=client,
            manifest=manifest,
            dry_run=args.dry_run,
        )
        print(f"DEM Ingestion Result: {res_dem}")


if __name__ == "__main__":
    main()
