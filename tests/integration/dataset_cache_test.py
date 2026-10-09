"""Exercise dataset caching against the local S3-compatible server."""

import json
from unittest.mock import Mock

import pytest
import s3fs

from cnems_inputs import zenodo


def test_s3_manifest_and_resource_materialization(fake_r2, tmp_path, monkeypatch):
    root, config = fake_r2
    mirror = root / config["bucket"] / "zenodo/example/10.5281-zenodo.12345"
    (mirror / "nested").mkdir(parents=True)
    (mirror / "nested/my archive.zip").write_bytes(b"test archive")
    (mirror / "datapackage.json").write_text(
        json.dumps(
            {
                "resources": [
                    {
                        "name": "archive",
                        "path": "https://zenodo.org/records/12345/files/nested/my%20archive.zip",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    filesystem = s3fs.S3FileSystem(
        key=config["access_key"],
        secret=config["secret_key"],
        endpoint_url=config["endpoint_url"],
    )
    monkeypatch.setattr(zenodo.s3fs, "S3FileSystem", Mock(return_value=filesystem))
    http = Mock(side_effect=AssertionError("Zenodo must not be contacted"))
    monkeypatch.setattr(zenodo, "urlopen", http)
    options = {
        "s3_cache": f"s3://{config['bucket']}/zenodo",
        "allow_zenodo": False,
        "doi_map": zenodo.ZenodoDoiMap({"example": "10.5281/zenodo.12345"}),
    }
    cache = zenodo.DatasetCache(tmp_path, **options)
    destination = cache.ensure_local("example", "archive")
    assert (
        destination == tmp_path / "example/10.5281-zenodo.12345/nested/my archive.zip"
    )
    assert destination.read_bytes() == b"test archive"
    with pytest.raises(FileNotFoundError, match="Zenodo is disabled"):
        cache._ensure_file("example", "missing.zip")

    monkeypatch.setattr(
        zenodo.s3fs,
        "S3FileSystem",
        Mock(side_effect=AssertionError("Network on local hit")),
    )
    fresh = zenodo.DatasetCache(tmp_path, **options)
    assert fresh.ensure_local("example", "archive") == destination
    http.assert_not_called()
