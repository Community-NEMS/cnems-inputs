"""Stub transformation pipeline for SupplyCurve.csv.

Reads a file from GitHub (soon to be Datastore...), then publishes it to R2.
"""

from logging import getLogger
from pathlib import Path

import pandas as pd
import polars as pl

from cnems_inputs.helpers import extract_csv_to_pl, load

# Establish logger
logger = getLogger(__name__)


def aggregate_supply_curve_regional(
    supply_curve_county: pl.LazyFrame,
    settings: dict,
    cw_lf: pl.LazyFrame,
    cwst_lf: pl.LazyFrame,
):
    """Aggregates supply curves from county to user-specified regional level.

    This was create_supplycurve_r from BlueSky.

    Args:
        supply_curve_county : data frame containing supply curves at the county-level
        settings : input settings

    Returns:
        data frame containing supply curves at user-specified regional level
    """
    frame = supply_curve_county.collect().to_pandas()
    # agg the data up to the model region level
    cwr = cw_lf.collect().to_pandas()
    frame = (
        pd.merge(frame, cwr, how="right", on=["FIPS_cnty"])
        .drop(columns=["FIPS_cnty"])
        .groupby(by=["tech", "region", "year", "step"], as_index=False)
        .sum()[["region", "tech", "step", "year", "SupplyCurve"]]
    )

    # create full index to merge to
    index = cwr.drop(columns=["FIPS_cnty"]).drop_duplicates()
    cwst = cwst_lf.collect().to_pandas().drop(columns=["count"])
    # TODO: ask Brian why this new row addition exists?
    new_row = pd.DataFrame({"tech": [15], "step": [2]})
    cwst = pd.concat([cwst, new_row], ignore_index=True)
    index = pd.merge(index, cwst, how="cross")
    index = pd.merge(
        index,
        pd.DataFrame(
            range(settings["first_year"], settings["last_year"] + 1), columns=["year"]
        ),
        how="cross",
    )

    frame = pd.merge(
        index, frame, on=["region", "tech", "step", "year"], how="left"
    ).fillna(0)
    return frame


def run_supply_curve_regional(
    supply_curve_county_path: str,
    cwst_path: str,
    cw_path: str,
    settings: dict,
    regional_output_path: Path,
):
    """E, T, L."""
    supply_curve_regional = aggregate_supply_curve_regional(
        supply_curve_county=extract_csv_to_pl(supply_curve_county_path),
        cw_lf=extract_csv_to_pl(cw_path),
        cwst_lf=extract_csv_to_pl(cwst_path),
        settings=settings,
    )
    load(supply_curve_regional, regional_output_path)


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_supply_curve_regional(
        supply_curve_county_path=snakemake.input["supply_curve_county_path"],
        cwst_path=snakemake.input["cwst_path"],
        cw_path=snakemake.input["cw_path"],
        settings=snakemake.params["settings"],
        regional_output_path=snakemake.output[0],
    )
