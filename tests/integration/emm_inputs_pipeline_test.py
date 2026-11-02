"""Integration tests for materializing EMM input tables."""

from collections.abc import Callable
from pathlib import Path
from zipfile import ZipFile

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from cnems_inputs.dataset_cache import DatasetCache


def test_enduse_base_share_matches_archived_source(
    materialize_input: Callable[[str], Path], dataset_cache: DatasetCache
) -> None:
    """The enduse_base_share pipeline should publish the source data with only the header changed."""
    actual = pl.read_csv(materialize_input("out__enduse_base_share"))
    archive_path = dataset_cache.ensure_local("eiabluesky", "eiabluesky-v1-1.zip")
    with (
        ZipFile(archive_path) as archive,
        archive.open("input/residential/EnduseBaseShares.csv") as source,
    ):
        # ignore the old column headers
        expected = pl.read_csv(source, new_columns=actual.columns)

    assert_frame_equal(actual, expected)


@pytest.mark.parametrize("rule_name", ["out__available_capacity", "out__base_load"])
def test_built_pipelines(
    rule_name: str,
    materialize_input: Callable[[str], Path],
    dataset_cache: DatasetCache,
) -> None:
    """Run the rules for the rebuilt pipelines and ensure there is a non-empty output."""
    df = pl.scan_csv(materialize_input(rule_name))
    assert not df.limit(1).collect().is_empty(), (
        f"{rule_name} should have made something"
    )


# NOTE (2026-09-15) we could probably add a "supply curve schema
# matches datapackage.json" test here, or even add that as part of the
# materialize_input fixture
