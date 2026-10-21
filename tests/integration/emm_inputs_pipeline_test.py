"""Integration tests for materializing EMM input tables."""

from collections.abc import Callable
from pathlib import Path
from zipfile import ZipFile

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from cnems_inputs.dataset_cache import DatasetCache


def test_enduse_base_share_matches_archived_source(
    materialize_input: Callable[[str], Path],
    dataset_cache: DatasetCache,
) -> None:
    """The enduse_base_share pipeline should publish the source data unchanged."""
    actual = pl.read_csv(materialize_input("out__enduse_base_share"))
    archive_path = dataset_cache.ensure_local("eiabluesky", "eiabluesky-v1-1.zip")
    with (
        ZipFile(archive_path) as archive,
        archive.open("input/residential/EnduseBaseShares.csv") as source,
    ):
        expected = pl.read_csv(source)

    assert_frame_equal(actual, expected)


@pytest.mark.xfail()
def test_build_available_capacity(
    materialize_input: Callable[[str], Path],
    test_fixture_dir: Path,
) -> None:
    """The available capacity pipeline should build the output.

    This does not work right now! It will only work once we setup datastore-like
    tooling such that pytest can grab all of the needed inputs (without having
    to always use zenodo because, flaky).
    """
    available_capacity = pl.read_csv(materialize_input("core__available_capacity"))
    assert not available_capacity.empty


# NOTE (2026-09-15) we could probably add a "supply curve schema
# matches datapackage.json" test here, or even add that as part of the
# materialize_input fixture
