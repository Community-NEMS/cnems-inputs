"""Integration tests for materializing EMM input tables."""

from collections.abc import Callable
from pathlib import Path
from zipfile import ZipFile

import polars as pl
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


def test_built_pipelines(
    materialize_input: Callable[[str], Path],
    dataset_cache: DatasetCache,
) -> None:
    """The available capacity pipeline should build the output."""
    pipelines = ["available_capacity", "base_load"]
    for pipeline in pipelines:
        df = pl.read_csv(materialize_input(f"out__{pipeline}"))
        assert not df.is_empty(), f"{pipeline} should have made something"


# NOTE (2026-09-15) we could probably add a "supply curve schema
# matches datapackage.json" test here, or even add that as part of the
# materialize_input fixture
