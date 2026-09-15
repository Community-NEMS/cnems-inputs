"""Integration tests for materializing EMM input tables."""

from collections.abc import Callable
from pathlib import Path

import polars as pl
from polars.testing import assert_frame_equal


def test_supply_curve_matches_fixture(
    materialize_input: Callable[[str], Path],
    test_fixture_dir: Path,
) -> None:
    """The supply curve pipeline should publish the source data unchanged."""
    expected_path = (
        test_fixture_dir
        / "eiabluesky"
        / "input"
        / "electricity"
        / "cem_inputs"
        / "SupplyCurve.csv"
    )

    actual = pl.read_csv(materialize_input("supply_curve"))
    expected = pl.read_csv(expected_path)

    assert_frame_equal(actual, expected)


# NOTE (2026-09-15) we could probably add a "supply curve schema
# matches datapackage.json" test here, or even add that as part of the
# materialize_input fixture
