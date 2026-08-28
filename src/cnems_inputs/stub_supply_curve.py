"""Stub transformation pipeline for SupplyCurve.csv.

Reads a file from GitHub (soon to be Datastore...), then publishes it to R2.
"""

from pathlib import Path
from zipfile import ZipFile

import polars as pl
from upath import UPath


def extract(archive_path: UPath, member_path: str) -> pl.LazyFrame:
    """Make a LazyFrame from a file within a ZIP archive.

    archive_path: path to the ZIP archive itself. Since we're using the
        Datastore to cache files, this is likely a local path but *could* be a
        remote path depending on cache layer configuration.
    member_path: the file name within the ZIP archive.
    """
    with UPath(archive_path).open("rb") as blob, ZipFile(blob) as zf:
        content = zf.open(member_path)
        return pl.scan_csv(content)


def transform(raw: pl.LazyFrame) -> pl.LazyFrame:
    """Do nothing."""
    return raw


def load(transformed: pl.LazyFrame, output_path: Path) -> None:
    """Write LazyFrame to output.

    transformed: the data we want to write out.
    output_path: a path for us to write the data out to, which may then be
        pushed remotely via the storage backend configured for this output.
    """
    transformed.sink_csv(output_path)


def run(input_path, output_path, resource_path):
    """E, T, L."""
    load(
        transform(extract(archive_path=input_path, resource_path=resource_path)),
        output_path,
    )


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run(snakemake.input[0], snakemake.output[0], snakemake.params["resource_path"])
