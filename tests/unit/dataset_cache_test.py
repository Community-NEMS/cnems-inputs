"""Test pinned dataset caching without external services."""

import io
import json
import multiprocessing
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from filelock import FileLock, Timeout

from cnems_inputs import zenodo


@pytest.fixture
def cache(tmp_path: Path) -> zenodo.DatasetCache:
    return zenodo.DatasetCache(
        tmp_path,
        doi_map=zenodo.ZenodoDoiMap({"example": "10.5281/zenodo.12345"}),
    )


def _seed_manifest(cache: zenodo.DatasetCache, url: str | None = None) -> Path:
    root = cache.cache_dir / "example/10.5281-zenodo.12345"
    root.mkdir(parents=True, exist_ok=True)
    (root / "datapackage.json").write_text(
        json.dumps(
            {
                "resources": [
                    {
                        "name": "archive",
                        "path": url
                        or "https://zenodo.org/records/12345/files/archive.zip",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return root


def test_local_hit_never_uses_network(cache, monkeypatch):
    root = _seed_manifest(cache)
    (root / "archive.zip").write_bytes(b"cached archive")
    network = Mock(side_effect=AssertionError("Network used on local hit"))
    monkeypatch.setattr(zenodo.s3fs, "S3FileSystem", network)
    monkeypatch.setattr(zenodo, "urlopen", network)

    assert cache.ensure_local("example", "archive") == root / "archive.zip"
    assert cache.ensure_local("example", "archive").read_bytes() == b"cached archive"
    network.assert_not_called()


def test_s3_fetches_manifest_and_file_then_uses_local_cache(cache, monkeypatch):
    def get_file(url, path):
        content = (
            json.dumps(
                {
                    "resources": [
                        {
                            "name": "archive",
                            "path": zenodo.resolve(
                                "example", "archive.zip", doi_map=cache.doi_map
                            ),
                        }
                    ]
                }
            ).encode()
            if url.endswith("datapackage.json")
            else b"archive content"
        )
        Path(path).write_bytes(content)

    s3 = Mock()
    s3.get_file.side_effect = get_file
    monkeypatch.setattr(zenodo.s3fs, "S3FileSystem", Mock(return_value=s3))
    http = Mock(side_effect=AssertionError("Zenodo used on S3 hit"))
    monkeypatch.setattr(zenodo, "urlopen", http)

    result = cache.ensure_local("example", "archive")
    assert result.read_bytes() == b"archive content"
    assert [call.args[0] for call in s3.get_file.call_args_list] == [
        "s3://pudl.catalyst.coop/zenodo/example/10.5281-zenodo.12345/datapackage.json",
        "s3://pudl.catalyst.coop/zenodo/example/10.5281-zenodo.12345/archive.zip",
    ]
    s3.get_file.side_effect = AssertionError("S3 used on local hit")
    assert cache.ensure_local("example", "archive") == result
    # A fresh instance also reads its manifest locally.
    fresh = zenodo.DatasetCache(cache.cache_dir, doi_map=cache.doi_map)
    assert fresh.ensure_local("example", "archive") == result
    http.assert_not_called()


def test_s3_miss_falls_back_to_zenodo(cache, monkeypatch):
    root = _seed_manifest(cache)
    s3 = Mock()
    s3.get_file.side_effect = FileNotFoundError("No such object")
    monkeypatch.setattr(zenodo.s3fs, "S3FileSystem", Mock(return_value=s3))
    http = Mock(return_value=io.BytesIO(b"Zenodo archive"))
    monkeypatch.setattr(zenodo, "urlopen", http)

    assert cache.ensure_local("example", "archive").read_bytes() == b"Zenodo archive"
    http.assert_called_once_with(
        "https://zenodo.org/records/12345/files/archive.zip", timeout=30
    )
    assert not list(root.glob(".archive.zip.*"))


@pytest.mark.parametrize(
    "error", [PermissionError("Access denied"), TimeoutError("S3 timeout")]
)
def test_s3_operational_error_propagates(cache, monkeypatch, error):
    root = _seed_manifest(cache)
    s3 = Mock()
    s3.get_file.side_effect = error
    monkeypatch.setattr(zenodo.s3fs, "S3FileSystem", Mock(return_value=s3))
    http = Mock(side_effect=AssertionError("Unexpected fallback"))
    monkeypatch.setattr(zenodo, "urlopen", http)

    with pytest.raises(type(error), match=str(error)):
        cache.ensure_local("example", "archive")
    assert not (root / "archive.zip").exists()
    assert not list(root.glob(".archive.zip.*"))
    http.assert_not_called()


@pytest.mark.parametrize("s3_cache", [None, "s3://mirror/zenodo"])
def test_missing_file_with_zenodo_disabled(cache, monkeypatch, s3_cache):
    cache.allow_zenodo = False
    cache.s3_cache = s3_cache
    s3 = Mock()
    s3.get_file.side_effect = FileNotFoundError("No such object")
    monkeypatch.setattr(zenodo.s3fs, "S3FileSystem", Mock(return_value=s3))
    http = Mock(side_effect=AssertionError("Zenodo is disabled"))
    monkeypatch.setattr(zenodo, "urlopen", http)

    with pytest.raises(FileNotFoundError, match="Zenodo is disabled.*datapackage.json"):
        cache.ensure_local("example", "archive")
    http.assert_not_called()


def test_interrupted_download_is_not_published_and_can_retry(cache, monkeypatch):
    root = _seed_manifest(cache)

    def interrupt(dataset, relative_path, key, destination):
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
        lambda dataset, relative_path, key, destination: destination.write_bytes(
            b"complete"
        ),
    )
    assert cache.ensure_local("example", "archive").read_bytes() == b"complete"


def test_resource_url_preserves_nested_paths_and_decodes_escaping(cache):
    _seed_manifest(
        cache,
        "https://zenodo.org/records/12345/files/nested/my%20archive.zip?download=1",
    )
    resource = cache.get_resource_metadata("example", "archive")
    assert resource.relative_path == "nested/my archive.zip"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/records/12345/files/archive.zip",
        "https://zenodo.org/records/99999/files/archive.zip",
        "http://zenodo.org/records/12345/files/archive.zip",
        "https://zenodo.org/records/12345/files-other/archive.zip",
        "https://zenodo.org/records/12345/files/%2e%2e/archive.zip",
        "https://zenodo.org/records/12345/files/%2Farchive.zip",
    ],
)
def test_invalid_resource_url_raises(cache, url):
    _seed_manifest(cache, url)
    with pytest.raises(ValueError):
        cache.get_resource_metadata("example", "archive")


def test_unknown_resource_raises(cache):
    _seed_manifest(cache)
    with pytest.raises(KeyError, match="unknown"):
        cache.get_resource_metadata("example", "unknown")


def test_new_doi_uses_different_local_files(cache):
    root = _seed_manifest(cache)
    (root / "archive.zip").write_bytes(b"old version")
    new = zenodo.DatasetCache(
        cache.cache_dir,
        doi_map=zenodo.ZenodoDoiMap({"example": "10.5281/zenodo.67890"}),
        s3_cache=None,
        allow_zenodo=False,
    )
    with pytest.raises(FileNotFoundError, match="10.5281-zenodo.67890"):
        new.ensure_local("example", "archive")


def test_zenodo_fetch_without_s3(cache, monkeypatch):
    _seed_manifest(cache)
    cache.s3_cache = None
    monkeypatch.setattr(zenodo, "urlopen", Mock(return_value=io.BytesIO(b"archive")))
    assert cache.ensure_local("example", "archive").read_bytes() == b"archive"


def test_concurrent_callers_download_once(tmp_path):
    context = multiprocessing.get_context("spawn")
    started = context.Event()
    release = context.Event()
    contended = context.Event()
    downloads = context.Value("i", 0)
    results = context.Queue()
    args = (tmp_path, started, release, contended, downloads, results)
    first = context.Process(target=_cache_worker, args=(*args, False))
    second = context.Process(target=_cache_worker, args=(*args, True))
    destination = tmp_path / "example/10.5281-zenodo.12345/archive.zip"
    try:
        first.start()
        assert started.wait(15), "First caller did not start downloading"
        second.start()
        assert contended.wait(15), "Second caller did not encounter the held lock"
        assert downloads.value == 1
        assert not destination.exists()
        release.set()
        replies = [results.get(timeout=15), results.get(timeout=15)]
        first.join(timeout=15)
        second.join(timeout=15)
        assert first.exitcode == second.exitcode == 0
        assert replies == [(str(destination), b"complete archive")] * 2
        assert downloads.value == 1
        assert not list(destination.parent.glob(".archive.zip.*"))
    finally:
        release.set()
        for process in (first, second):
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=15)
        results.close()
        results.join_thread()


def _cache_worker(
    cache_dir, started, release, contended, downloads, results, instrument_lock
):
    class ObservedLock(FileLock):
        def acquire(self, *args, **kwargs):
            try:
                return super().acquire(timeout=0)
            except Timeout:
                contended.set()
                return super().acquire(*args, **kwargs)

    def download(self, dataset, relative_path, key, destination):
        with downloads.get_lock():
            downloads.value += 1
        destination.write_bytes(b"partial archive")
        started.set()
        assert release.wait(15), "Parent did not release the download"
        destination.write_bytes(b"complete archive")

    cache = zenodo.DatasetCache(
        cache_dir, doi_map=zenodo.ZenodoDoiMap({"example": "10.5281/zenodo.12345"})
    )
    with (
        patch.object(zenodo.DatasetCache, "_download", download),
        patch.object(zenodo, "FileLock", ObservedLock if instrument_lock else FileLock),
    ):
        destination = cache._ensure_file("example", "archive.zip")
        results.put((str(destination), destination.read_bytes()))
