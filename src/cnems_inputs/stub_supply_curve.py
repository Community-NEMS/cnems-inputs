"""Stub transformation pipeline for SupplyCurve.csv.

Reads a file from GitHub (soon to be Datastore...), then publishes it to R2.
"""

from pathlib import Path
from zipfile import ZipFile

import polars as pl
from upath import UPath


def extract(zip_path: UPath) -> pl.LazyFrame:
    """Make a LazyFrame from the input path.

    We want to read the data *at extraction time*, not at definition time, so we get the zip_path as the HTTP path, not a local cached path.

    NOTE (2026-08-19): consider using the cached-http storage plugin!
    """
    with UPath(zip_path).open("rb") as blob, ZipFile(blob) as zf:
        content = zf.open("input/electricity/cem_inputs/SupplyCurve.csv")
        return pl.scan_csv(content)


def transform(raw: pl.LazyFrame) -> pl.LazyFrame:
    """Do nothing."""
    return raw


def load(transformed: pl.LazyFrame, output_path: Path) -> None:
    """Write LazyFrame to output.

    Note that here, we've set the S3 storage plugin to `retrieve=True`. This
    means that we write to a local cached path, and the S3 storage plugin will read
    from that path and write to the configured location.

    We use the S3 storage plugin because that lets Snakemake better understand
    which outputs have been built vs. need rebuilding.
    """
    transformed.sink_csv(output_path)


def run(input_path, output_path):
    """E, T, L."""
    load(transform(extract(input_path)), output_path)


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run(snakemake.input[0], snakemake.output[0])
