"""Assorted helper functions that shouldn't live in Snakefile."""

import datetime as dt
import json
import os
from pathlib import Path
from typing import Literal

import pandas as pd
import polars as pl

from cnems_inputs.schema import schema_for


# Set CNEMS_INPUT_VERSION_ID env var to publish to a specific version prefix.
#
# NOTE (2026-08-28): we *could* do some fancy parsing of the git rev here if we
# really want, but setting env var in GHA seemed easier
def versioned_r2_uri(bucket: str, path: str) -> str:
    """Given a path to publish to, generate the right R2 URI.

    * correct version prefix - set CNEMS_INPUT_VERSION_ID to publish to a
      specific prefix; defaults to nightly
    * correct bucket
    """
    version = os.getenv("CNEMS_INPUT_VERSION_ID", "nightly")
    return f"s3://{bucket}/{version}/{path}"


def load(
    transformed: pd.DataFrame,
    output_path: Path,
    datapackage_path: Path | None = None,
    resource_name: str | None = None,
) -> None:
    """Write DataFrame to output.

    Parameters:
        transformed: the data we want to write out.
        output_path: a path for us to write the data out to, which may then be
            pushed remotely via the storage backend configured for this output.
        datapackage_path: Optional; if specified, path to datapackage for validation.
        resource_name: Optional; if specified, validate the transformed data frame
            against the corresponding datapackage schema before writing out the file
            to the output path.
    """
    if datapackage_path and resource_name:
        # then do schema enforcement
        transformed = schema_for(datapackage_path, resource_name).validate(transformed)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    transformed.to_csv(output_path, index=False)


def get_published_paths(datapackage_path: str) -> list[str]:
    """Get resource paths defined within a datapackage."""
    with Path(datapackage_path).open() as dp:
        datapackage = json.load(dp)
    return [r["path"] for r in datapackage["resources"]]


def get_published_path_for_resource(datapackage_path: str, resource_name: str) -> str:
    """Get resource path specified by a datapackage."""
    with Path(datapackage_path).open() as dp:
        datapackage = json.load(dp)
    # there are <100 of these so we can worst case examine all of them
    for resource in datapackage["resources"]:
        if resource["name"] == resource_name:
            return resource["path"]
    raise ValueError(
        f"No resource called {resource_name} found in datapackage at {datapackage_path}"
    )


def filter_eia_by_report_date(
    df_eia: pl.DataFrame,
    eia_month: Literal["max"] | dt.date,
    data_maturity: Literal["monthly_update", "final"] | None,
) -> pl.DataFrame:
    """Filter a monthly or yearly reported EIA table on a given month or 'max'.

    Using 'max' as the ``eia_month``is a nice shorthand for getting the most up-to-date
    data. The most up-to-date data from the monthly EIA-860M releases do not contain all
    of the values from EIA-923, so you can use the ``data_maturity`` argument to first
    filter the data to the final data (aka the full annually reported EIA data).
    """
    if data_maturity:
        df_eia = df_eia.filter(pl.col("data_maturity") == "final")

    if eia_month == "max":
        month_filter = pl.col("report_date") == pl.col("report_date").max()
    else:
        eia_month = (
            dt.datetime.strptime(str(eia_month), "%Y-%m-%d").astimezone(dt.UTC).date()
        )
        month_filter = pl.col("report_date") == eia_month

    return df_eia.filter(month_filter)


def filter_eia_by_report_year(
    df_eia: pl.DataFrame,
    eia_year: Literal["max"] | int,
    data_maturity: Literal["monthly_update", "final"] | None,
) -> pl.DataFrame:
    """Filter a monthly reported EIA table on a given year or 'max'.

    Using 'max' as the ``eia_year``is a nice shorthand for getting the most up-to-date
    data. The most up-to-date data from the monthly EIA-860M releases do not contain all
    of the values from EIA-923, so you can use the ``data_maturity`` argument to first
    filter the data to the final data (aka the full annually reported EIA data).
    """
    if data_maturity:
        df_eia = df_eia.filter(pl.col("data_maturity") == "final")

    if eia_year == "max":
        year_filter = (
            pl.col("report_date").dt.year() == pl.col("report_date").dt.year().max()
        )
    else:
        year_filter = pl.col("report_date").dt.year() == eia_year

    df_eia = df_eia.filter(year_filter)
    assert not df_eia.is_empty(), (
        f"The given {eia_year=} and {data_maturity=} resulted in an empty dataframe. "
        "Consider altering the config in emm_inputs.yaml."
    )
    return df_eia


def merge_tech_label_on_technology_description(
    df: pl.DataFrame, crosswalk_tech: pl.DataFrame
) -> pl.DataFrame:
    """Merge a table with an EIA technology_description with the tech crosswalk."""
    # Rename the BlueSky EIA technology name to the PUDL name. This is used for
    # merging in the
    crosswalk_tech = crosswalk_tech.rename({"Technology": "technology_description"})
    # ensure the crosswalk has at least the two columns we need.
    assert set(crosswalk_tech.columns).issuperset({"tech", "technology_description"})

    df = df.join(crosswalk_tech, on="technology_description", how="left")

    # all of these do not have a Technology
    missing_tech = df.filter(pl.col("tech").is_null())
    assert (len(missing_tech) < 21) and missing_tech.filter(
        pl.col("technology_description").is_not_null()
    ).is_empty(), (
        "We expect to have a small number of records with missing tech value "
        f"and all of those should have a null technology but we found {len(missing_tech)}:"
        f"\n\n {missing_tech.select(['plant_id_eia', 'generator_id', 'technology_description', 'report_date'])}"
    )
    return df


def fill_in_missing_regions_with_most_frequent_state_region(
    frame: pl.DataFrame,
    crosswalk_region: pl.DataFrame,
    expected_missing_num: int,
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
    if (missing_region_len := missing_region.shape[0]) > expected_missing_num:
        raise AssertionError(
            f"Found {missing_region_len} county_id_fips codes which do not correspond "
            "to the county_id_fips in the crosswalk_region, but expected "
            f"{expected_missing_num} or less.\n\n\n{missing_region}"
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
    still_null = frame.filter(pl.col("region").is_null())
    assert still_null.is_empty(), (
        "We still have nulls in the region column... Something went wrong here\n\n"
        f"{still_null}"
    )
    return frame
