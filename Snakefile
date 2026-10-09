storage r2:
  provider="s3",
  endpoint_url=config["r2"]["endpoint_url"],
  access_key=config["r2"]["access_key"],
  secret_key=config["r2"]["secret_key"]

from cnems_inputs.zenodo import DatasetCache
from cnems_inputs.helpers import get_published_paths, versioned_r2_uri
from collections.abc import Callable
import logging

dataset_logger = logging.getLogger("cnems_inputs.zenodo")
dataset_logger.setLevel(logging.INFO)
if not dataset_logger.hasHandlers():
    dataset_logger.addHandler(logging.StreamHandler())

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
    allow_zenodo=config.get("allow_zenodo", True),
)

def resolve_dataset(dataset: str, resource_name: str) -> Callable[[object], str]:
    """Return an input callable that materializes the named file during DAG evaluation."""
    return lambda wildcards: str(dataset_cache.ensure_local(dataset, resource_name))

include: "electricity_market_model.smk"
