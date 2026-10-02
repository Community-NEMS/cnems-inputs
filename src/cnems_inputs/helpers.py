"""Assorted helper functions that shouldn't live in Snakefile."""

import os
from zipfile import ZipFile

import polars as pl
from upath import UPath


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


def extract_from_zip(archive_path: str, resource_path: str) -> pl.LazyFrame:
    """Make a LazyFrame from a file within a ZIP archive.

    archive_path: path to the ZIP archive itself. Since we're using the
        Datastore to cache files, this is likely a local path but *could* be a
        remote path depending on cache layer configuration.
    resource_path: the file name within the ZIP archive.
    """
    with UPath(archive_path).open("rb") as blob, ZipFile(blob) as zf:
        content = zf.open(resource_path)
        return pl.scan_csv(content)


def extract_parquet_to_pl(path: str) -> pl.DataFrame:
    """Read a parquet file as a polars DataFrame."""
    return pl.read_parquet(path)
