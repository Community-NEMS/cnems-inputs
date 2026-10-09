"""Utilities for schema validation."""

import json
from pathlib import Path

from pandera.api.pandas.container import DataFrameSchema
from pandera.io.pandas_io import from_frictionless_schema


def schema_for(resource_name: str) -> DataFrameSchema:
    """Look up and return the Pandera schema for the specified resource."""
    with Path("datapackage.json").open() as f:
        dpkg = json.load(f)
    matching = [r for r in dpkg["resources"] if r["name"] == resource_name]
    if not matching:
        raise ValueError(f"No resource with name '{resource_name}'")
    return from_frictionless_schema(matching[0]["schema"])
