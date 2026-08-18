"""Stub transformation pipeline for SupplyCurve.csv.

Reads a file from GitHub (soon to be Datastore...), then publishes it to R2.
"""

from pathlib import Path

import polars as pl


def extract(input_path: Path) -> pl.LazyFrame:
    """Make a LazyFrame from the input path.

    Note that we've set the HTTP storage engine to `retrieve=False`. This means
    that *we* handle the remote fetching with Polars, rather than having Snakemake
    handle remote fetching to a local cached location. This allows us to have
    partial remote reads using Polars predicate/projection pushdown.
    """
    return pl.scan_csv(input_path)


def transform(raw: pl.LazyFrame) -> pl.LazyFrame:
    """Do nothing."""
    return raw


def load(transformed: pl.LazyFrame, output_path: Path) -> None:
    """Write LazyFrame to output.

    Note that here, we've set the S3 storage engine to `retrieve=True`. This
    means that we write to a local cached path, and the S3 storage plugin will read
    from that path and write to the configured location.
    """
    transformed.sink_csv(output_path)


def run(input_path, output_path):
    """E, T, L."""
    load(transform(extract(input_path)), output_path)


if __name__ == "__main__":
    from snakemake.iocontainers import snakemake

    run(snakemake.input[0], snakemake.output[0])
