# Design Decisions and Conventions

## Rule naming

Snakemake rule names pertaining to published resources should be double-underscore (`__`) delimited and contain the following fields:

1. Layer/stage; one of `raw` `core` `out`
    - `raw` for data originally produced outside this repository
    - `core` for cleaned intermediate files, useful for validation or debugging
    - `out` for publishable files that meet the spec in the datapackage
1. Resource name; as listed in datapackage.json
1. [Optional] Descriptive slug; e.g. the type of region aggregation

For example, there are two rules for available capacity,

- `core__available_capacity__county`
    - Stage is `core`
    - Resource name is `available_capacity`
    - Slug is `county`; this file contains data at the county level,
        ready for aggregation to larger regions.
- `out__available_capacity`
    - Stage is `out`
    - Resource name is `available_capacity`
    - Slug is not used

This naming convention lets us use the datapackage file to store properties of each resource,
such as output path and data types,
and look them up wherever they are needed.

## Script naming

Wherever possible, make the script name match the rule name, or use the rule name as a prefix.

This naming convention helps quickly move between the Snakemake file and the `src/` directory,
when you need to know the rule definition for a script, or the script details for a rule.
It also helps make it more obvious when a script file is no longer needed.

### Script template

The following is a general-purpose template which includes all of our script conventions.
Start with this and replace `x`, inputs, outputs, settings, etc to suit the pipeline
you are writing.

```python
"""Transformation pipeline for x."""

import polars as pl

from pathlib import Path

from cnems_inputs.helpers import load


def transform_x(
    x_input_df: pl.LazyFrame,
    settings: dict,
) -> pl.LazyFrame:
    """Compute [x] from [inputs]."""
    return x_input_df


def run_x(
    settings: dict,
    x_input_path: str,
    x_output_path: Path,
    datapackage_path: str,  # needed for out resources
):
    """E, T, L."""
    x = transform_x(x_input_df=pl.scan_parquet(x_input_path), settings=settings)

    # pick one
    load(x.collect().to_pandas(), x_output_path)  # for core resources
    load(
        x.collect().to_pandas(), x_output_path, Path(datapackage_path), "x"
    )  # for out resources -- activates validation


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_x(
        settings=snakemake.params["settings"],
        x_output_path=Path(snakemake.output[0]),
        **snakemake.input,
    )
```
