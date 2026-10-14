storage cached_http:
  provider="cached-http",
  cache=config.get("cached_http_cache", ".snakemake/storage/cached-http/cache")

storage r2:
  provider="s3",
  endpoint_url=config["r2"]["endpoint_url"],
  access_key=config["r2"]["access_key"],
  secret_key=config["r2"]["secret_key"]

storage s3:
  provider="http", # 2026-10-02 S3 provider doesn't support anonymous requests so we go HTTP instead

import polars as pl

from cnems_inputs.zenodo import cache_path, resolve
from cnems_inputs.helpers import get_published_paths, versioned_r2_uri

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

def resolve_dataset(dataset: str, resource_path: str) -> str:
    """Resolve a resource within a dataset to its URL.

    The dataset is matched up with its DOI defined in
    src/cnems_inputs/zenodo_dois.yaml.

    If zenodo_source config is set to "remote", the default, we register these
    URLs with Snakemake storage.

    If it is set to "cache" (via `--config zenodo_source=cache`) we return the
    path to the existing local cache instead, avoiding network calls.

    Most of the actual logic lives in `cnems_inputs.zenodo.resolve` - this just
    provides the glue to Snakemake storage.

    Args:
        dataset: Dataset name configured in the DOI map.
        resource_path: Path to desired resource relative to the dataset's
            Zenodo record.
    """
    # NOTE (2026-08-26): If we ever use non-Zenodo DOI providers we'll need to
    # dispatch properly.
    url = resolve(dataset, resource_path)
    zenodo_source = config.get("zenodo_source", "remote")
    if zenodo_source == "remote":
        return storage.cached_http(url)
    if zenodo_source == "cache":
        return str(cache_path(url, cache_dir=storage._storages["cached_http"].settings.cache))
    raise ValueError("zenodo_source must be 'remote' or 'cache'")

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
