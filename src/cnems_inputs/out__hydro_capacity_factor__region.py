"""Aggregate county-level hydro capacity factor data into regions using regional crosswalk."""

from pathlib import Path

import polars as pl

from cnems_inputs.helpers import (
    fill_in_missing_regions_with_most_frequent_state_region,
    load,
)


def transform_hydro_capacity_factor_region(
    core__hydro_capacity_factor__county: pl.DataFrame, crosswalk_region: pl.DataFrame
):
    """Aggregates base-load from county to user-specified regional level."""
    crosswalk_region = crosswalk_region.rename(
        {"FIPS_cnty": "county_id_fips"}
    ).with_columns(county_id_fips=pl.col("county_id_fips").str.zfill(5))

    hydro_region = (
        core__hydro_capacity_factor__county.join(
            crosswalk_region, how="left", on=["county_id_fips"]
        )
        # Remove hawaii counties? and alaska?
        .filter(
            ~pl.col("county_id_fips").str.starts_with("15")
            & ~pl.col("county_id_fips").str.starts_with("02")
            & pl.col("county_id_fips").is_not_null()
        )
        .pipe(
            fill_in_missing_regions_with_most_frequent_state_region,
            crosswalk_region,
            expected_missing_num=11,
        )
        .group_by(["region", "season"])
        .agg(
            # weighted average for capacity_factor
            (
                pl.col("hydro_capacity_factor_frac").dot(pl.col("capacity_mw"))
                / pl.col("capacity_mw").sum()
            ).alias("hydro_capacity_factor_frac"),
        )
        .sort(["region", "season"])
        .with_columns(notes=pl.lit(None).cast(pl.String))
    )
    return hydro_region.to_pandas()


def run_hydro_capacity_factor__region(
    core__hydro_capacity_factor__county_path: str,
    crosswalk_region_path: str,
    datapackage_path: Path,
    region_output_path: Path,
):
    """E, T, L.

    Attempting to be analogous to: BlueSky/sample/baseload_data_pipeline/scripts/agg_EMMregions.csv
    """
    hydro_capacity_factor_region = transform_hydro_capacity_factor_region(
        core__hydro_capacity_factor__county=pl.read_csv(
            core__hydro_capacity_factor__county_path,
            schema_overrides={"county_id_fips": pl.String},
        ),
        crosswalk_region=pl.read_csv(
            crosswalk_region_path,
            schema_overrides={"FIPS_cnty": pl.String, "region": pl.Int64},
        ),
    )

    load(
        hydro_capacity_factor_region,
        region_output_path,
        datapackage_path=datapackage_path,
        resource_name="hydro_capacity_factor",
    )


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_hydro_capacity_factor__region(
        core__hydro_capacity_factor__county_path=snakemake.input[
            "core__hydro_capacity_factor__county_path"
        ],
        crosswalk_region_path=snakemake.input["crosswalk_region_path"],
        datapackage_path=Path(snakemake.input["datapackage_path"]),
        region_output_path=Path(snakemake.output[0]),
    )
