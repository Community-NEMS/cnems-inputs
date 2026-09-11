"""Assorted helper functions that shouldn't live in Snakefile."""

import os


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
