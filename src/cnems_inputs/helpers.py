"""Assorted helper functions that shouldn't live in Snakefile."""

import json
import os
from pathlib import Path

import pandas as pd

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
    transformed: pd.DataFrame, output_path: Path, resource_name: str | None = None
) -> None:
    """Write DataFrame to output.

    transformed: the data we want to write out.
    output_path: a path for us to write the data out to, which may then be
        pushed remotely via the storage backend configured for this output.
    """
    if resource_name:
        # then do schema enforcement
        schema_for(resource_name).validate(transformed)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    transformed.to_csv(output_path, index=False)


def get_published_paths(datapackage_path: str) -> list[str]:
    """Get resource paths defined within a datapackage."""
    with Path(datapackage_path).open() as dp:
        datapackage = json.load(dp)
    return [r["path"] for r in datapackage["resources"]]
