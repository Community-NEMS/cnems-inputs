"""Test pinned dataset caching without external services."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import ANY, Mock, call, patch

import pytest

from cnems_inputs import dataset_cache


def _populate_local(
    cache: dataset_cache.DatasetCache,
    files: dict[str, str],
    *,
    dataset: str = "example",
    doi: str = "10.5281/zenodo.12345",
) -> None:
    """Dump files where local cache expects them.

    This doesn't spit out a Mock like the remote cache guys below, because we
    are actually writing to disk, just in a temporary location.
    """
    root = cache.cache_dir / dataset / doi.replace("/", "-")
    for name, content in files.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)


def _remote_files(files: dict[str, str]) -> Mock:
    """Return helper to mock out remote file access.

    It's a Mock, not just a normal function, so the calls are instrumented and
    we can make assertions about them.
    """

    def download(url: str, destination: Path) -> None:
        if url not in files:
            raise FileNotFoundError(url)
        destination.write_text(files[url])

    return Mock(side_effect=download)


@contextmanager
def _mock_s3(
    cache: dataset_cache.DatasetCache,
    files: dict[str, str],
    *,
    dataset: str = "example",
    doi: str = "10.5281/zenodo.12345",
) -> Iterator[Mock]:
    """Mock out S3 file access and expose the downloader within a context."""
    prefix = f"{cache.s3_cache}/{dataset}/{doi.replace('/', '-')}"
    mock = _remote_files(
        {f"{prefix}/{name}": content for name, content in files.items()}
    )
    with patch.object(type(cache), "_download_from_s3", mock):
        yield mock


@contextmanager
def _mock_zenodo(
    cache: dataset_cache.DatasetCache,
    files: dict[str, str],
    *,
    doi: str = "10.5281/zenodo.12345",
) -> Iterator[Mock]:
    """Mock out Zenodo file access and expose the downloader within a context."""
    record_url = dataset_cache._zenodo_record_url(doi)
    mock = _remote_files(
        {f"{record_url}/files/{name}": content for name, content in files.items()}
    )
    with patch.object(type(cache), "_download_from_zenodo", mock):
        yield mock


@pytest.fixture
def cache(tmp_path: Path) -> dataset_cache.DatasetCache:
    return dataset_cache.DatasetCache(
        tmp_path,
        doi_map=dataset_cache.ZenodoDoiMap({"example": "10.5281/zenodo.12345"}),
    )


def _datapackagify(
    resources: dict[str, str],
    record_url: str = "https://zenodo.org/records/12345/files",
) -> str:
    """Make a stripped-down datapackage JSON.

    - `resources` looks like `{"archive_name": "relpath"}`
    - `record_url` is the base URL to glue that onto
    """
    return json.dumps(
        {
            "resources": [
                {"name": name, "path": f"{record_url}/{relpath}"}
                for name, relpath in resources.items()
            ]
        }
    )


# Set up some useful file records for parametrizing
manifest_file = {"datapackage.json": _datapackagify({"archive": "archive.zip"})}
archive_file = {"archive.zip": "archive content"}
both_files = manifest_file | archive_file


@pytest.mark.parametrize(
    ("local_files", "s3_files", "zenodo_files"),
    [
        pytest.param(both_files, {}, {}, id="local-hit"),
        pytest.param({}, both_files, {}, id="s3-hit"),
        pytest.param({}, {}, both_files, id="zenodo-hit"),
        pytest.param(manifest_file, both_files, {}, id="local-manifest-s3-resource"),
        pytest.param({}, manifest_file, both_files, id="s3-manifest-zenodo-resource"),
    ],
)
def test_cache_always_populates_local(
    cache: dataset_cache.DatasetCache,
    local_files: dict[str, str],
    s3_files: dict[str, str],
    zenodo_files: dict[str, str],
) -> None:
    """Make sure ensure_local does populate the local cache.

    * initialize the apparent local/s3/zenodo caches
    * see if first ensure_local() call gets expected content
    * call ensure_local() again and make sure no s3/zenodo access happens
    """
    root = cache.cache_dir / "example/10.5281-zenodo.12345"
    _populate_local(cache, local_files)
    with _mock_s3(cache, s3_files) as s3, _mock_zenodo(cache, zenodo_files) as zenodo:
        result = cache.ensure_local("example", "archive")
        assert result == root / "archive.zip"
        assert result.read_text() == "archive content"
        assert (root / "datapackage.json").read_text() == manifest_file[
            "datapackage.json"
        ]

        s3.reset_mock()
        zenodo.reset_mock()
        assert cache.ensure_local("example", "archive") == result
        assert result.read_text() == "archive content"

        fresh = dataset_cache.DatasetCache(cache.cache_dir, doi_map=cache.doi_map)
        assert fresh.ensure_local("example", "archive") == result
        assert result.read_text() == "archive content"

        # should not have been called either by old *or* new cache
        s3.assert_not_called()
        zenodo.assert_not_called()


def test_interrupted_download_leaves_no_trace(
    cache: dataset_cache.DatasetCache, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If you interrupt a download it shouldn't leave a corrupt file behind.

    Mock out the download method to fail partway through a download.

    Then make sure:
    * no file is at the final-download location
    * the temp file doesn't exist either
    """
    root = cache.cache_dir / "example/10.5281-zenodo.12345"
    _populate_local(cache, manifest_file)

    def interrupt(
        record_url: str, relative_path: Path, key: Path, destination: Path
    ) -> None:
        destination.write_text("partial")
        raise ConnectionError("Interrupted")

    monkeypatch.setattr(cache, "_download", interrupt)
    with pytest.raises(ConnectionError, match="Interrupted"):
        cache.ensure_local("example", "archive")
    assert not (root / "archive.zip").exists()
    assert sorted(path.name for path in root.iterdir()) == ["datapackage.json"]


def test_new_doi_doesnt_collide(cache: dataset_cache.DatasetCache) -> None:
    """Even if the dataset/resource are the same, new DOI triggers re-cache.

    * add old and new content corresponding to different DOIs to local cache
    * make a new DatasetCache instance pointing at new DOI
    * old/new DatasetCache instances see different content
    """
    old_root = cache.cache_dir / "example/10.5281-zenodo.12345"
    new_root = cache.cache_dir / "example/10.5281-zenodo.67890"
    _populate_local(cache, {**manifest_file, "archive.zip": "old version"})
    _populate_local(
        cache,
        {
            "datapackage.json": _datapackagify(
                {"archive": "archive.zip"},
                record_url="https://zenodo.org/records/67890/files",
            ),
            "archive.zip": "new version",
        },
        doi="10.5281/zenodo.67890",
    )
    new_cache = dataset_cache.DatasetCache(
        cache.cache_dir,
        doi_map=dataset_cache.ZenodoDoiMap({"example": "10.5281/zenodo.67890"}),
    )
    with _mock_s3(cache, {}), _mock_zenodo(cache, {}):
        old_path = cache.ensure_local("example", "archive")
        new_path = new_cache.ensure_local("example", "archive")
        assert old_path == old_root / "archive.zip"
        assert new_path == new_root / "archive.zip"
        assert old_path.read_text() == "old version"
        assert new_path.read_text() == "new version"


@pytest.mark.parametrize(
    ("doi", "record_url"),
    [
        ("10.5281/zenodo.12345", "https://zenodo.org/records/12345"),
        ("10.5072/zenodo.12345", "https://sandbox.zenodo.org/records/12345"),
    ],
)
def test_manifest_url_conversion(tmp_path: Path, doi: str, record_url: str) -> None:
    """We want to get the right local/s3/zenodo URLs out of the manifest.

    Manifest paths are always absolute URLs, we try to split it into fragments
    and recombine.

    So let's throw it something CRAZY with slashes and spaces and make sure it
    still works.
    """
    cache = dataset_cache.DatasetCache(
        tmp_path, doi_map=dataset_cache.ZenodoDoiMap({"example": doi})
    )
    remote_files = {
        "datapackage.json": _datapackagify(
            {"archive": "nested/my%20archive.zip?download=1"},
            record_url=f"{record_url}/files",
        ),
        "nested/my%20archive.zip": "archive content",
    }

    # Don't populate local or S3, only Zenodo - force us to go through every cache layer
    with (
        _mock_s3(cache, {}, doi=doi) as s3,
        _mock_zenodo(cache, remote_files, doi=doi) as zenodo,
    ):
        result = cache.ensure_local("example", "archive")
        assert (
            result
            == tmp_path / "example" / doi.replace("/", "-") / "nested/my archive.zip"
        )
        assert result.read_text() == "archive content"
        s3_prefix = f"s3://pudl.catalyst.coop/zenodo/example/{doi.replace('/', '-')}"
        assert s3.call_args_list == [
            call(f"{s3_prefix}/datapackage.json", ANY),
            call(f"{s3_prefix}/nested/my archive.zip", ANY),
        ]
        assert zenodo.call_args_list == [
            call(f"{record_url}/files/datapackage.json", ANY),
            call(f"{record_url}/files/nested/my%20archive.zip", ANY),
        ]


def test_manifest_resource_must_match_pinned_record(
    cache: dataset_cache.DatasetCache,
) -> None:
    """Don't want to allow mismatched DOI paths in the datapackage."""
    _populate_local(
        cache,
        {
            "datapackage.json": _datapackagify(
                {"archive": "archive.zip"},
                record_url="https://zenodo.org/records/99999/files",
            )
        },
    )
    with _mock_s3(cache, {}) as s3, _mock_zenodo(cache, {}) as zenodo:
        with pytest.raises(ValueError, match="outside the pinned record"):
            cache.ensure_local("example", "archive")
        s3.assert_not_called()
        zenodo.assert_not_called()
