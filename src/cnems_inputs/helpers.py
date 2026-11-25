"""Assorted helper functions that shouldn't live in Snakefile."""

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


def adjust_dollars_for_inflation(
    dollar_data: pd.Series,
    cpi_data_lf: pl.LazyFrame,
    current_dollar_year: int,
    past_dollar_year: int,
) -> pd.Series:
    """Adjust nominal dollar data from one historical year to a desired one.

    Using BLS CPI data, do this by multiplying the original
    value x the CPI for the current year and dividing by the CPI for
    the past dollar year.
    """
    cpi_data = cpi_data_lf.collect()
    current_cpi = (
        cpi_data.filter(cpi_data["year"] == current_dollar_year).select("value").item()
    )
    former_cpi = (
        cpi_data.filter(cpi_data["year"] == past_dollar_year).select("value").item()
    )

    dollar_data = dollar_data * (current_cpi / former_cpi)
    return dollar_data
