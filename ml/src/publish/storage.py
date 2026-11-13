"""
HeatSafe-ML free-storage sync (Phases 9-10) using a Hugging Face Dataset repo.

Repo layout (repo id from thresholds.yaml `storage.repo_id`):
    latest.json                    pointer to the current product bundle
    bundles/<version>.tar          one product bundle (rasters, tiles, vectors, tables, manifest)
    state/pipeline_state.tar       what a fresh GitHub runner needs: model, terrain, climatology,
                                   scene index, seasonal maps, exposure layers

The write token is read from HEATSAFE_STORAGE_TOKEN and is never logged.

Usage:
    python -m ml.src.publish.storage upload-state
    python -m ml.src.publish.storage restore-state
    python -m ml.src.publish.storage upload-bundle
    python -m ml.src.publish.storage restore-bundle
"""

import argparse
import json
import os
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from ml.src.commons.logger import get_ml_logger
from ml.src.dataset.splits import load_thresholds
from ml.src.models.core.evaluate import sha256_file
from ml.src.publish.products import published_dir, read_latest, set_latest
from ml.src.validation.final_test import latest_model_dir

logging = get_ml_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
STATE_ARCHIVE = "state/pipeline_state.tar"
STATE_PATHS = (
    "ml/data/processed/scene_index.parquet",
    "ml/data/interim/static_terrain.npz",
    "ml/data/interim/index_climatology.npz",
    "ml/data/processed/maps",
    "ml/data/processed/exposure",
)


class StorageNotConfiguredError(RuntimeError):
    """
    Raised when no storage token is available.
    """


def get_token() -> str:
    """
    Read the storage token from the environment.

    Returns:
        str: The token (never logged).

    Raises:
        StorageNotConfiguredError: If HEATSAFE_STORAGE_TOKEN is unset or empty.
    """
    token = os.environ.get("HEATSAFE_STORAGE_TOKEN", "").strip()
    if not token:
        raise StorageNotConfiguredError("HEATSAFE_STORAGE_TOKEN is not set")
    return token


def storage_settings() -> dict[str, Any]:
    """
    Load the `storage` section of thresholds.yaml.

    Returns:
        dict[str, Any]: repo_id and keep_bundles.
    """
    return load_thresholds()["storage"]


def make_api(token: str) -> Any:
    """
    Create a Hugging Face API client.

    Args:
        token (str): Access token.

    Returns:
        Any: HfApi instance.
    """
    from huggingface_hub import HfApi

    return HfApi(token=token)


def skip_previews(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
    """
    Tar filter that leaves out PNG previews (not needed to run the pipeline).

    Args:
        info (tarfile.TarInfo): Entry being added.

    Returns:
        tarfile.TarInfo | None: The entry, or None to skip it.
    """
    return None if info.name.lower().endswith(".png") else info


def pack_tar(items: list[tuple[Path, str]], archive: Path, skip_png: bool = False) -> Path:
    """
    Write an uncompressed tar of files and folders.

    Args:
        items (list[tuple[Path, str]]): (local path, name inside the archive).
        archive (Path): Output tar file.
        skip_png (bool): Leave out PNG files (previews). Never set for bundles: their map tiles are PNGs.

    Returns:
        Path: The archive.

    Raises:
        FileNotFoundError: If an item does not exist.
    """
    with tarfile.open(archive, "w") as tar:
        for path, arcname in items:
            if not path.exists():
                raise FileNotFoundError(f"Cannot pack missing path: {path}")
            tar.add(path, arcname=arcname, filter=skip_previews if skip_png else None)
    return archive


def unpack_tar(archive: Path, destination: Path) -> None:
    """
    Extract a tar safely (the `data` filter rejects absolute paths, links outside the target, and devices).

    Args:
        archive (Path): Tar file.
        destination (Path): Folder to extract into.
    """
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r") as tar:
        tar.extractall(destination, filter="data")


def verify_bundle(bundle: Path) -> bool:
    """
    Check every file of a bundle against its manifest.

    Args:
        bundle (Path): Bundle folder holding `manifest.json`.

    Returns:
        bool: True if all files exist with the recorded SHA-256.
    """
    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return all((bundle / f["path"]).is_file() and sha256_file(bundle / f["path"]) == f["sha256"]
               for f in manifest["files"])


def state_items(root: Path = REPO_ROOT) -> list[tuple[Path, str]]:
    """
    Files and folders a fresh runner needs, including the newest registered model.

    Args:
        root (Path): Repository root.

    Returns:
        list[tuple[Path, str]]: (local path, archive name) pairs.
    """
    items = [(root / rel, rel) for rel in STATE_PATHS]
    model_dir = latest_model_dir(root / "ml" / "models" / "registry")
    items.append((model_dir, f"ml/models/registry/{model_dir.name}"))
    return items


def upload_state(api: Any | None = None, root: Path = REPO_ROOT) -> dict[str, Any]:
    """
    Upload the pipeline state archive.

    Args:
        api (Any | None): API client (defaults to a real one using the stored token).
        root (Path): Repository root.

    Returns:
        dict[str, Any]: repo path and size in bytes.
    """
    api = api or make_api(get_token())
    repo_id = storage_settings()["repo_id"]
    with tempfile.TemporaryDirectory() as tmp:
        archive = pack_tar(state_items(root), Path(tmp) / "state.tar", skip_png=True)
        size = archive.stat().st_size
        api.upload_file(path_or_fileobj=str(archive), path_in_repo=STATE_ARCHIVE, repo_id=repo_id,
                        repo_type="dataset", commit_message="Update pipeline state")
    logging.info(f"Uploaded pipeline state ({size / 1e6:.1f} MB) to {repo_id}")
    return {"path": STATE_ARCHIVE, "bytes": size}


def restore_state(api: Any | None = None, root: Path = REPO_ROOT) -> dict[str, Any]:
    """
    Download and extract the pipeline state archive into the repository.

    Args:
        api (Any | None): API client.
        root (Path): Repository root.

    Returns:
        dict[str, Any]: repo path restored.
    """
    api = api or make_api(get_token())
    repo_id = storage_settings()["repo_id"]
    with tempfile.TemporaryDirectory() as tmp:
        local = api.hf_hub_download(repo_id=repo_id, filename=STATE_ARCHIVE, repo_type="dataset", local_dir=tmp)
        unpack_tar(Path(local), root)
    logging.info(f"Restored pipeline state from {repo_id}")
    return {"path": STATE_ARCHIVE}


def prune_old_bundles(api: Any, repo_id: str, keep: int) -> list[str]:
    """
    Delete the oldest bundle archives, keeping the newest `keep` (versions start with the scene date).

    Args:
        api (Any): API client.
        repo_id (str): Dataset repo id.
        keep (int): Number of bundles to keep.

    Returns:
        list[str]: Deleted repo paths.
    """
    bundles = sorted(f for f in api.list_repo_files(repo_id=repo_id, repo_type="dataset")
                     if f.startswith("bundles/") and f.endswith(".tar"))
    removed = bundles[: max(0, len(bundles) - keep)]
    for path in removed:
        api.delete_file(path_in_repo=path, repo_id=repo_id, repo_type="dataset",
                        commit_message="Prune old product bundle")
    return removed


def upload_bundle(bundle: Path, api: Any | None = None) -> dict[str, Any]:
    """
    Upload a product bundle and then the pointer that makes it current.

    The pointer is uploaded last, so a reader never sees a pointer to a missing bundle.

    Args:
        bundle (Path): Bundle folder (must verify against its manifest).
        api (Any | None): API client.

    Returns:
        dict[str, Any]: version, bytes, and pruned paths.

    Raises:
        ValueError: If the bundle does not verify against its manifest.
    """
    if not verify_bundle(bundle):
        raise ValueError(f"Bundle {bundle.name} does not match its manifest; refusing to upload")
    api = api or make_api(get_token())
    settings = storage_settings()
    repo_id = settings["repo_id"]
    pointer = read_latest(bundle.parent)
    if pointer is None or pointer["version"] != bundle.name:
        raise ValueError("latest.json does not point at this bundle")
    with tempfile.TemporaryDirectory() as tmp:
        archive = pack_tar([(bundle, bundle.name)], Path(tmp) / "bundle.tar")
        size = archive.stat().st_size
        api.upload_file(path_or_fileobj=str(archive), path_in_repo=f"bundles/{bundle.name}.tar", repo_id=repo_id,
                        repo_type="dataset", commit_message=f"Add bundle {bundle.name}")
    api.upload_file(path_or_fileobj=json.dumps(pointer, indent=1).encode("utf-8"), path_in_repo="latest.json",
                    repo_id=repo_id, repo_type="dataset", commit_message=f"Point latest at {bundle.name}")
    removed = prune_old_bundles(api, repo_id, int(settings["keep_bundles"]))
    logging.info(f"Uploaded bundle {bundle.name} ({size / 1e6:.1f} MB); pruned {len(removed)} old bundle(s)")
    return {"version": bundle.name, "bytes": size, "pruned": removed}


def restore_latest_bundle(api: Any | None = None, root: Path | None = None) -> dict[str, Any]:
    """
    Download the current bundle (if not already present and intact) and write the local pointer.

    Args:
        api (Any | None): API client.
        root (Path | None): Published folder (defaults to the configured one).

    Returns:
        dict[str, Any]: version and whether a download was needed.

    Raises:
        ValueError: If the downloaded bundle fails verification.
    """
    api = api or make_api(get_token())
    root = root or published_dir()
    repo_id = storage_settings()["repo_id"]
    with tempfile.TemporaryDirectory() as tmp:
        pointer_file = api.hf_hub_download(repo_id=repo_id, filename="latest.json", repo_type="dataset", local_dir=tmp)
        pointer = json.loads(Path(pointer_file).read_text(encoding="utf-8"))
        version = pointer["version"]
        downloaded = False
        if not verify_bundle(root / version):
            local = api.hf_hub_download(repo_id=repo_id, filename=f"bundles/{version}.tar",
                                        repo_type="dataset", local_dir=tmp)
            unpack_tar(Path(local), root)
            downloaded = True
            if not verify_bundle(root / version):
                raise ValueError(f"Downloaded bundle {version} failed manifest verification")
    set_latest(root, pointer)
    logging.info(f"Latest bundle {version} ready (downloaded={downloaded})")
    return {"version": version, "downloaded": downloaded}


def main() -> None:
    """
    Command-line entry point.
    """
    parser = argparse.ArgumentParser(description="Sync HeatSafe-ML data with the free Hugging Face dataset repo")
    parser.add_argument("action", choices=["upload-state", "restore-state", "upload-bundle", "restore-bundle"])
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
    if args.action == "upload-state":
        result = upload_state()
    elif args.action == "restore-state":
        result = restore_state()
    elif args.action == "restore-bundle":
        result = restore_latest_bundle()
    else:
        pointer = read_latest(published_dir())
        if pointer is None:
            raise SystemExit("Nothing published yet")
        result = upload_bundle(published_dir() / pointer["version"])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
