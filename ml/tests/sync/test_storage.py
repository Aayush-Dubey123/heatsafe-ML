import json
import shutil
import tarfile
from pathlib import Path

import pytest

from ml.src.publish.products import read_latest, set_latest, write_manifest
from ml.src.sync import storage

REPO = "owner/test-repo"


class FakeApi:
    """
    In-memory stand-in for the Hugging Face API client.
    """

    def __init__(self) -> None:
        """
        Start with an empty repo.
        """
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def upload_file(self, path_or_fileobj, path_in_repo, repo_id, repo_type, commit_message):
        """
        Store an uploaded file (path or bytes).
        """
        assert repo_id == REPO and repo_type == "dataset"
        data = path_or_fileobj if isinstance(path_or_fileobj, bytes) else Path(path_or_fileobj).read_bytes()
        self.files[path_in_repo] = data

    def hf_hub_download(self, repo_id, filename, repo_type, local_dir):
        """
        Write a stored file into local_dir and return its path.
        """
        target = Path(local_dir) / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.files[filename])
        return str(target)

    def list_repo_files(self, repo_id, repo_type):
        """
        List stored paths.
        """
        return list(self.files)

    def delete_file(self, path_in_repo, repo_id, repo_type, commit_message):
        """
        Remove a stored file.
        """
        self.deleted.append(path_in_repo)
        del self.files[path_in_repo]


@pytest.fixture(autouse=True)
def fixed_settings(monkeypatch):
    """
    Use a test repo id and keep two bundles.
    """
    monkeypatch.setattr(storage, "storage_settings", lambda: {"repo_id": REPO, "keep_bundles": 2})


def make_bundle(root: Path, version: str) -> Path:
    """
    Build a small verified bundle and point latest.json at it.
    """
    bundle = root / version
    (bundle / "cogs").mkdir(parents=True)
    (bundle / "cogs" / "a.tif").write_bytes(b"raster-" + version.encode())
    (bundle / "preview.png").write_bytes(b"png")
    write_manifest(bundle, {"version": version, "scene_date": "2026-11-03"})
    set_latest(root, {"version": version, "scene_date": "2026-11-03", "stale": False})
    return bundle


def test_bundle_round_trip_and_pointer_last(tmp_path: Path):
    """
    A bundle uploaded to the fake repo can be restored elsewhere, verified, and made latest.
    """
    api = FakeApi()
    source = make_bundle(tmp_path / "src", "2026-11-03_a")
    result = storage.upload_bundle(source, api=api)
    assert result["version"] == "2026-11-03_a"
    assert list(api.files) == ["bundles/2026-11-03_a.tar", "latest.json"]

    target = tmp_path / "dst"
    restored = storage.restore_latest_bundle(api=api, root=target)
    assert restored == {"version": "2026-11-03_a", "downloaded": True}
    assert storage.verify_bundle(target / "2026-11-03_a")
    assert (target / "2026-11-03_a" / "preview.png").read_bytes() == b"png"  # bundle tiles are PNGs: must survive
    assert read_latest(target)["version"] == "2026-11-03_a"
    assert storage.restore_latest_bundle(api=api, root=target)["downloaded"] is False


def test_old_bundles_are_pruned_keeping_newest_two(tmp_path: Path):
    """
    Uploading a third bundle removes the oldest archive.
    """
    api = FakeApi()
    for version in ("2026-10-01_a", "2026-10-15_b", "2026-11-03_c"):
        storage.upload_bundle(make_bundle(tmp_path / "src", version), api=api)
    assert sorted(f for f in api.files if f.startswith("bundles/")) == ["bundles/2026-10-15_b.tar",
                                                                          "bundles/2026-11-03_c.tar"]
    assert api.deleted == ["bundles/2026-10-01_a.tar"]


def test_upload_refuses_corrupt_or_unpointed_bundle(tmp_path: Path):
    """
    A bundle whose file changed after hashing, or that latest.json does not point to, is not uploaded.
    """
    api = FakeApi()
    bundle = make_bundle(tmp_path / "src", "v1")
    (bundle / "cogs" / "a.tif").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="manifest"):
        storage.upload_bundle(bundle, api=api)
    other = make_bundle(tmp_path / "src2", "v2")
    set_latest(tmp_path / "src2", {"version": "other"})
    with pytest.raises(ValueError, match="latest.json"):
        storage.upload_bundle(other, api=api)
    assert api.files == {}


def test_restore_rejects_bundle_that_fails_verification(tmp_path: Path):
    """
    A downloaded archive whose contents do not match the manifest is refused.
    """
    api = FakeApi()
    source = make_bundle(tmp_path / "src", "v1")
    storage.upload_bundle(source, api=api)
    broken = tmp_path / "broken"
    shutil.copytree(source, broken / "v1")
    (broken / "v1" / "cogs" / "a.tif").write_bytes(b"bad")
    archive = storage.pack_tar([(broken / "v1", "v1")], tmp_path / "b.tar")
    api.files["bundles/v1.tar"] = archive.read_bytes()
    with pytest.raises(ValueError, match="verification"):
        storage.restore_latest_bundle(api=api, root=tmp_path / "dst")


def test_unpack_blocks_path_traversal(tmp_path: Path):
    """
    A tar entry trying to escape the target folder is rejected.
    """
    evil = tmp_path / "evil.tar"
    with tarfile.open(evil, "w") as tar:
        info = tarfile.TarInfo("../escaped.txt")
        data = b"x"
        info.size = len(data)
        import io

        tar.addfile(info, io.BytesIO(data))
    with pytest.raises(tarfile.TarError):
        storage.unpack_tar(evil, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists()


def test_state_round_trip_skips_previews(tmp_path: Path, monkeypatch):
    """
    State files travel through storage; PNG previews are left out.
    """
    root = tmp_path / "repo"
    (root / "ml/data/processed/maps").mkdir(parents=True)
    (root / "ml/data/processed/maps/lst.tif").write_bytes(b"tif")
    (root / "ml/data/processed/maps/lst.png").write_bytes(b"png")
    monkeypatch.setattr(storage, "STATE_PATHS", ("ml/data/processed/maps",))
    model = root / "ml/models/registry/m1-test"
    model.mkdir(parents=True)
    (model / "metadata.json").write_text("{}")
    api = FakeApi()
    storage.upload_state(api=api, root=root)
    fresh = tmp_path / "fresh"
    storage.restore_state(api=api, root=fresh)
    assert (fresh / "ml/data/processed/maps/lst.tif").read_bytes() == b"tif"
    assert not (fresh / "ml/data/processed/maps/lst.png").exists()
    assert (fresh / "ml/models/registry/m1-test/metadata.json").is_file()


def test_token_is_required_and_never_in_logs(monkeypatch):
    """
    Without a token the storage layer raises a clear error.
    """
    monkeypatch.delenv("HEATSAFE_STORAGE_TOKEN", raising=False)
    with pytest.raises(storage.StorageNotConfiguredError):
        storage.get_token()
    monkeypatch.setenv("HEATSAFE_STORAGE_TOKEN", "  secret-value  ")
    assert storage.get_token() == "secret-value"
    assert json.dumps({"ok": True})
