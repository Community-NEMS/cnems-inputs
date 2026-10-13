storage r2:
  provider="s3",
  endpoint_url=config["r2"]["endpoint_url"],
  access_key=config["r2"]["access_key"],
  secret_key=config["r2"]["secret_key"]

storage s3:
  provider="http", # 2026-10-02 S3 provider doesn't support anonymous requests so we go HTTP instead

import polars as pl

from cnems_inputs.dataset_cache import DatasetCache
from cnems_inputs.helpers import get_published_paths, versioned_r2_uri
from collections.abc import Callable
import logging

dataset_logger = logging.getLogger("cnems_inputs.dataset_cache")
dataset_logger.setLevel(logging.INFO)
if not dataset_logger.handlers:
    dataset_logger.addHandler(logging.StreamHandler())

OUTPUT_BUCKET = config["r2"]["bucket"]

def r2(path: str) -> str:
    """Hook up snakemake storage.r2 plugin to the R2 URI helper.

    The R2 URI helper is pure normal Python and just munges strings together.
    `storage.r2` and `config` are only available in Snakefiles, so we wrap
    the pure function here.

    `storage.r2()`... returns a string, but also has the side-effect of
    registering the file with the Snakemake storage system.
    """
    return storage.r2(versioned_r2_uri(config["r2"]["bucket"], path))

dataset_cache = DatasetCache(
    cache_dir=config.get("dataset_cache_dir", ".snakemake/zenodo"),
    s3_cache=config.get("dataset_s3_cache", "s3://pudl.catalyst.coop/zenodo"),
)

def resolve_dataset(dataset: str, resource_name: str) -> Callable[[object], str]:
    """Return input function that ensures a resource is cached locally.

    We don't just call ensure_local and return a string here, since that would
    mean *all* inputs are checked at DAG collection time whenever we run any
    rule. This way, merely all inputs *for the upstream subgraph* get checked.
    """
    return lambda wildcards: str(dataset_cache.ensure_local(dataset, resource_name))

def pudl(version: str, table_name: str) -> str:
    """Read a PUDL table from aws for a given version.

    Args:
        version: PUDL version. `stable` is recommended. If `nightly`, then this will grab
            the most recent which is freshest but less stable. You can also pin to
            specific version for extra stability.
        table_name: the pudl table name.
    """
    return storage.s3(f"https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/{version}/{table_name}.parquet")


include: "electricity_market_model.smk"
