"""Test pinned dataset caching without external services."""

import json
from pathlib import Path
from unittest.mock import ANY, Mock

import pytest

from cnems_inputs import dataset_cache


@pytest.fixture
def cache(tmp_path: Path) -> dataset_cache.DatasetCache:
    return dataset_cache.DatasetCache(
        tmp_path,
        doi_map=dataset_cache.ZenodoDoiMap({"example": "10.5281/zenodo.12345"}),
    )


def test_cached_reads_stay_local_across_instances(cache, monkeypatch):
    """Once we warm the cache on disk, we should never hit _download even if we
    recreate the DatasetCache accessor."""
    root = _populate_datapackage(cache, {"local_archive": "local_archive.zip"})
    (root / "local_archive.zip").write_bytes(b"cached archive")
    monkeypatch.setattr(dataset_cache.DatasetCache, "_download", _unexpected_download)

    fresh = dataset_cache.DatasetCache(cache.cache_dir, doi_map=cache.doi_map)
    for reader in (cache, fresh):
        result = reader.ensure_local("example", "local_archive")
        assert result == root / "local_archive.zip"
        assert result.read_bytes() == b"cached archive"


def test_s3_miss_falls_back_to_zenodo(cache, monkeypatch):
    root = _populate_datapackage(cache, {"archive": "archive.zip"})
    s3 = Mock(side_effect=FileNotFoundError("No such S3 object"))
    remote = Mock(
        side_effect=lambda url, destination: destination.write_bytes(b"Zenodo archive")
    )
    monkeypatch.setattr(cache, "_download_from_s3", s3)
    monkeypatch.setattr(cache, "_download_from_zenodo", remote)

    result = cache.ensure_local("example", "archive")
    assert result == root / "archive.zip"
    assert result.read_bytes() == b"Zenodo archive"
    # second arg is the temp filename, we don't need to check it.
    s3.assert_called_once_with(
        "s3://pudl.catalyst.coop/zenodo/example/10.5281-zenodo.12345/archive.zip", ANY
    )
    remote.assert_called_once_with(
        "https://zenodo.org/records/12345/files/archive.zip", ANY
    )


def test_s3_fetches_manifest_and_resource(cache, monkeypatch):
    s3_root = "s3://pudl.catalyst.coop/zenodo/example/10.5281-zenodo.12345"
    s3 = _remote_files(
        {
            f"{s3_root}/datapackage.json": _datapackage(
                {"archive": "https://zenodo.org/records/12345/files/archive.zip"}
            ),
            f"{s3_root}/archive.zip": b"S3 archive",
        }
    )
    monkeypatch.setattr(cache, "_download_from_s3", s3)
    monkeypatch.setattr(cache, "_download_from_zenodo", _unexpected_download)

    result = cache.ensure_local("example", "archive")
    assert (
        result == cache.cache_dir / "example" / "10.5281-zenodo.12345" / "archive.zip"
    )
    assert result.read_bytes() == b"S3 archive"
    assert [request.args[0] for request in s3.call_args_list] == [
        f"{s3_root}/datapackage.json",
        f"{s3_root}/archive.zip",
    ]


def test_interrupted_download(cache, monkeypatch):
    root = _populate_datapackage(cache, {"archive": "archive.zip"})

    def interrupt(record_url, relative_path, key, destination):
        destination.write_bytes(b"partial")
        raise ConnectionError("Interrupted")

    monkeypatch.setattr(cache, "_download", interrupt)
    with pytest.raises(ConnectionError, match="Interrupted"):
        cache.ensure_local("example", "archive")
    assert not (root / "archive.zip").exists()
    assert not list(root.glob(".archive.zip.*"))

    monkeypatch.setattr(
        cache,
        "_download",
        lambda record_url, relative_path, key, destination: destination.write_bytes(
            b"complete"
        ),
    )
    assert cache.ensure_local("example", "archive").read_bytes() == b"complete"


def test_local_hit_decodes_nested_resource_url(cache):
    root = _populate_datapackage(
        cache,
        {"archive": "nested/my%20archive.zip?download=1"},
    )
    destination = root / "nested" / "my archive.zip"
    destination.parent.mkdir()
    destination.write_bytes(b"archive")
    assert cache.ensure_local("example", "archive") == destination


def test_manifest_resource_must_match_pinned_record(cache, monkeypatch):
    root = cache.cache_dir / "example" / "10.5281-zenodo.12345"
    root.mkdir(parents=True)
    (root / "datapackage.json").write_bytes(
        _datapackage({"archive": "https://zenodo.org/records/99999/files/archive.zip"})
    )
    monkeypatch.setattr(cache, "_download", _unexpected_download)
    with pytest.raises(ValueError, match="outside the pinned record"):
        cache.ensure_local("example", "archive")


def test_new_doi_does_not_reuse_previous_version(cache, monkeypatch):
    old_version_root = _populate_datapackage(cache, {"archive": "archive.zip"})
    (old_version_root / "archive.zip").write_bytes(b"old version")
    cache_new_doi = dataset_cache.DatasetCache(
        cache.cache_dir,
        doi_map=dataset_cache.ZenodoDoiMap({"example": "10.5281/zenodo.67890"}),
        s3_cache=None,
    )
    record_url = "https://zenodo.org/records/67890/files"
    remote = _remote_files(
        {
            f"{record_url}/datapackage.json": _datapackage(
                {"archive": f"{record_url}/archive.zip"}
            ),
            f"{record_url}/archive.zip": b"new version",
        }
    )
    monkeypatch.setattr(cache_new_doi, "_download_from_zenodo", remote)

    new_destination_archive_path = cache_new_doi.ensure_local("example", "archive")
    assert (
        new_destination_archive_path
        == cache.cache_dir / "example/10.5281-zenodo.67890/archive.zip"
    )
    assert new_destination_archive_path.read_bytes() == b"new version"
    assert (old_version_root / "archive.zip").read_bytes() == b"old version"


@pytest.mark.parametrize(
    ("doi", "record_url"),
    [
        ("10.5281/zenodo.12345", "https://zenodo.org/records/12345"),
        ("10.5072/zenodo.12345", "https://sandbox.zenodo.org/records/12345"),
    ],
)
def test_zenodo_fetches_manifest_and_resource_from_doi_host(
    tmp_path, monkeypatch, doi, record_url
):
    cache = dataset_cache.DatasetCache(
        tmp_path, s3_cache=None, doi_map=dataset_cache.ZenodoDoiMap({"example": doi})
    )
    resource_url = f"{record_url}/files/nested/my%20archive.zip"

    remote = _remote_files(
        {
            f"{record_url}/files/datapackage.json": _datapackage(
                {"archive": resource_url}
            ),
            resource_url: b"archive content",
        }
    )
    monkeypatch.setattr(cache, "_download_from_zenodo", remote)
    monkeypatch.setattr(cache, "_download_from_s3", _unexpected_download)

    destination = cache.ensure_local("example", "archive")
    assert (
        destination
        == tmp_path / "example" / doi.replace("/", "-") / "nested" / "my archive.zip"
    )
    assert destination.read_bytes() == b"archive content"
    assert [request.args[0] for request in remote.call_args_list] == [
        f"{record_url}/files/datapackage.json",
        resource_url,
    ]


def test_cache_uses_packaged_doi_map(tmp_path):
    cache = dataset_cache.DatasetCache(tmp_path)
    assert cache.doi_map.root["eiabluesky"] == "10.5281/zenodo.21629428"


def _populate_datapackage(
    cache: dataset_cache.DatasetCache, paths: dict[str, str]
) -> Path:
    """Seed a local manifest from names and paths relative to the pinned record."""
    root = cache.cache_dir / "example" / "10.5281-zenodo.12345"
    root.mkdir(parents=True, exist_ok=True)

    (root / "datapackage.json").write_bytes(
        _datapackage(
            {
                name: f"https://zenodo.org/records/12345/files/{path}"
                for name, path in paths.items()
            }
        )
    )
    return root


def _datapackage(paths: dict[str, str]) -> bytes:
    """Serialize resource names and explicit URLs into a minimal manifest."""
    return json.dumps(
        {"resources": [{"name": name, "path": path} for name, path in paths.items()]}
    ).encode("utf-8")


def _remote_files(files: dict[str, bytes]) -> Mock:
    """Serve only the supplied URLs and record requests for test assertions."""

    def download(url, destination):
        destination.write_bytes(files[url])

    return Mock(side_effect=download)


def _unexpected_download(*args):
    """Fail immediately when a test's excluded download path is used."""
    raise AssertionError("Unexpected download")
