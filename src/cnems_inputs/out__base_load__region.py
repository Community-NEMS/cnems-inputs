"""Aggregate county-level base load data into regions using regional crosswalk."""

from pathlib import Path

import polars as pl

from cnems_inputs.helpers import (
    fill_in_missing_regions_with_most_frequent_state_region,
    load,
)


def aggregate_base_load_region(
    core__base_load__county: pl.DataFrame, crosswalk_region: pl.DataFrame
):
    """Aggregates base-load from county to user-specified regional level.

    Analogous to `BlueSky/sample/baseload_data_pipeline/scripts/agg_EMMregions.sum_data_r`
    """
    crosswalk_region = crosswalk_region.rename({"FIPS_cnty": "county_id_fips"})

    frame = (
        core__base_load__county.join(
            crosswalk_region, how="left", on=["county_id_fips"]
        )
        .pipe(
            fill_in_missing_regions_with_most_frequent_state_region,
            crosswalk_region,
            expected_missing_num=5,
        )
        .group_by(["region", "hour"])
        .agg(pl.col("base_load_mwh").sum())
        .sort(["region", "hour"])
    )
    return frame.to_pandas()


def transform_base_load_region(
    core__base_load_county: pl.DataFrame, crosswalk_region: pl.DataFrame
):
    """Aggregate base load to the regional level."""
    # TODO: if nothing else needs to be done we probable shouldn't keep this layer
    return aggregate_base_load_region(core__base_load_county, crosswalk_region)


def run_base_load__region(
    core__base_load_county_path: str,
    crosswalk_region_path: str,
    datapackage_path: Path,
    region_output_path: Path,
):
    """E, T, L.

    Attempting to be analogous to: BlueSky/sample/baseload_data_pipeline/scripts/agg_EMMregions.csv
    """
    base_load_region = transform_base_load_region(
        core__base_load_county=pl.read_csv(core__base_load_county_path),
        crosswalk_region=pl.read_csv(crosswalk_region_path),
    )

    load(
        base_load_region,
        region_output_path,
        datapackage_path=datapackage_path,
        resource_name="base_load",
    )


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_base_load__region(
        core__base_load_county_path=snakemake.input["core__base_load_county_path"],
        crosswalk_region_path=snakemake.input["crosswalk_region_path"],
        datapackage_path=Path(snakemake.input["datapackage_path"]),
        region_output_path=Path(snakemake.output[0]),
    )
