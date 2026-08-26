"""Tests for Zenodo dataset URL resolution."""

import pytest
from pydantic import ValidationError

from cnems_inputs import zenodo


def test_resolve_known_dataset_from_default_config() -> None:
    assert (
        zenodo.resolve("eiabluesky", "eiabluesky-v1-1.zip")
        == "https://zenodo.org/records/21629428/files/eiabluesky-v1-1.zip"
    )


def test_resolve_accepts_custom_doi_map() -> None:
    doi_map = zenodo.ZenodoDoiMap({"test-dataset": "10.5072/zenodo.12345"})

    assert (
        zenodo.resolve(
            "test-dataset",
            "relative/path/to file.zip",
            doi_map=doi_map,
        )
        == "https://sandbox.zenodo.org/records/12345/files/relative/path/to%20file.zip"
    )


def test_zenodo_doi_map_validates_dois() -> None:
    with pytest.raises(ValidationError, match="String should match pattern"):
        zenodo.ZenodoDoiMap({"bad-dataset": "not-a-doi"})


def test_resolve_unknown_dataset() -> None:
    with pytest.raises(KeyError, match="unknown"):
        zenodo.resolve("unknown", "archive.zip")


@pytest.mark.parametrize(
    "relative_path",
    [
        "",
        ".",
        "/archive.zip",
        "../archive.zip",
        "dir/../archive.zip",
        "https://example.com/archive.zip",
    ],
)
def test_resolve_rejects_non_relative_paths(relative_path: str) -> None:
    with pytest.raises(ValueError, match="must be relative"):
        zenodo.resolve("eiabluesky", relative_path)
