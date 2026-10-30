"""Utilities for schema validation."""

import json
from pathlib import Path

from pandera.api.pandas.container import DataFrameSchema
from pandera.io.pandas_io import from_frictionless_schema


def schema_for(datapackage_path: Path, resource_name: str) -> DataFrameSchema:
    """Look up and return the Pandera schema for the specified resource."""
    with datapackage_path.open() as f:
        dpkg = json.load(f)
    matching = [r for r in dpkg["resources"] if r["name"] == resource_name]
    if not matching:
        raise ValueError(f"No resource with name '{resource_name}'")
    schema = from_frictionless_schema(matching[0]["schema"])
    for col in schema.columns.values():
        # the default boolean dtype ('bool') is not nullable;
        # rewrite to the nullable one ('boolean')
        if schema.dtypes[col.name].type == "bool":
            col.dtype = "boolean"
    return schema
