"""Assorted helper functions that shouldn't live in Snakefile."""

import datetime as dt
import json
import os
from pathlib import Path

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


def filter_eia_by_report_date(df_eia: pl.DataFrame, eia_month) -> pl.DataFrame:
    """Filter a monthly reported EIA table on a given month or 'max'."""
    if eia_month == "max":
        month_filter = pl.col("report_date") == pl.col("report_date").max()
    else:
        eia_month = (
            dt.datetime.strptime(str(eia_month), "%Y-%m-%d").astimezone(dt.UTC).date()
        )
        month_filter = pl.col("report_date") == eia_month

    return df_eia.filter(month_filter)


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
