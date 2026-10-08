"""Transformation pipeline for supply_curve.csv.

This step takes the county-level supply curve and aggregates it to defined regions.
These regions are currently made from a crosswalk coming from the original BlueSky
repository.
"""

from logging import getLogger
from pathlib import Path

import pandas as pd
import polars as pl

from cnems_inputs.helpers import load

# Establish logger
logger = getLogger(__name__)


def aggregate_supply_curve_region(
    supply_curve_county: pl.LazyFrame,
    settings: dict,
    crosswalk_region_lf: pl.LazyFrame,
    crosswalk_steps_lf: pl.LazyFrame,
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
    crosswalk_region = crosswalk_region_lf.collect().to_pandas()
    frame = pd.merge(frame, crosswalk_region, how="left", on=["FIPS_cnty"])
    assert (missing_regions := frame[frame.region.isna()]).empty, (
        f"We expect there to be no missing regions by found {missing_regions['FIPS_cnty'].unique()}"
    )
    frame = frame.groupby(by=["tech", "region", "year", "step"], as_index=False).sum()[
        ["region", "tech", "step", "year", "SupplyCurve"]
    ]

    # create full index to merge to
    index = crosswalk_region.drop(columns=["FIPS_cnty"]).drop_duplicates()
    crosswalk_steps = crosswalk_steps_lf.collect().to_pandas().drop(columns=["count"])
    # TODO: ask Brian why this new row addition exists?
    new_row = pd.DataFrame({"tech": [15], "step": [2]})
    crosswalk_steps = pd.concat([crosswalk_steps, new_row], ignore_index=True)
    index = pd.merge(index, crosswalk_steps, how="cross")
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


def run_supply_curve_region(
    supply_curve_county_path: str,
    crosswalk_steps_path: str,
    crosswalk_region_path: str,
    settings: dict,
    regional_output_path: Path,
):
    """E, T, L."""
    supply_curve_regional = aggregate_supply_curve_region(
        supply_curve_county=pl.scan_csv(supply_curve_county_path),
        crosswalk_region_lf=pl.scan_csv(crosswalk_region_path),
        crosswalk_steps_lf=pl.scan_csv(crosswalk_steps_path),
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

    run_supply_curve_region(
        supply_curve_county_path=snakemake.input["supply_curve_county_path"],
        crosswalk_steps_path=snakemake.input["crosswalk_steps_path"],
        crosswalk_region_path=snakemake.input["crosswalk_region_path"],
        settings=snakemake.params["settings"],
        regional_output_path=snakemake.output[0],
    )
