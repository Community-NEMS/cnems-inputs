"""Aggregate county-level base load data into regions using regional crosswalk."""

from pathlib import Path

import polars as pl

from cnems_inputs.helpers import load


def fill_in_missing_regions_with_most_frequent_state_region(
    frame: pl.DataFrame, crosswalk_region: pl.DataFrame
) -> pl.DataFrame:
    """Fill in missing regions using the most frequent region from the state.

    Once we try to join the crosswalk_region table (a small map between county's and
    region) with the county-level base load data, we can fill in any non-mapped
    counties based on whatever the most frequently reported region in the state.

    TODO: we could update this with the neighboring fips codes if we use shape files
    for fips codes.
    """
    make_state_id_fips_col = (
        pl.col("county_id_fips").cast(pl.String).str.head(2).alias("state_id_fips")
    )
    missing_region = (
        frame.filter(pl.col("region").is_null())
        .select(["county_id_fips"])
        .unique()
        .with_columns(make_state_id_fips_col)
    )
    if (missing_region_len := missing_region.shape[0]) > 5:
        raise AssertionError(
            f"Found {missing_region_len} county_id_fips codes which do not correspond "
            "to the county_id_fips in the crosswalk_region, but expected 5 or less."
        )
    most_frequent_region_by_state = (
        crosswalk_region.with_columns(make_state_id_fips_col)
        .filter(
            pl.col("state_id_fips").is_in(
                missing_region.get_column("state_id_fips").to_list()
            )
        )
        .group_by("state_id_fips")
        .agg(pl.col("region").mode().first())
        .join(
            missing_region,
            on=["state_id_fips"],
            how="left",
        )
        .drop("state_id_fips")
    )
    frame = frame.update(most_frequent_region_by_state, on="county_id_fips")
    assert not frame.get_column("region").has_nulls(), (
        "We still have nulls in the region column... Something went wrong here"
    )
    return frame


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
        .pipe(fill_in_missing_regions_with_most_frequent_state_region, crosswalk_region)
        .group_by(["region", "hour"])
        .agg(pl.col("base_load_mwh").sum())
        .sort(["region", "hour"])
        # TODO: Remove when we merge in #92
        .rename({"base_load_mwh": "Load"})
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
