storage cached_http:
  provider="cached-http",
  cache=config.get("cached_http_cache", ".snakemake/storage/cached-http/cache")

storage r2:
  provider="s3",
  endpoint_url=config["r2"]["endpoint_url"],
  access_key=config["r2"]["access_key"],
  secret_key=config["r2"]["secret_key"]

from cnems_inputs.zenodo import cache_path, resolve
from cnems_inputs.helpers import versioned_r2_uri

import polars as pl

OUTPUT_BUCKET = config["r2"]["bucket"]

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

# TODO: OKAYYYY SNAKKKEE. I need to make you into a thing that stores this file
# either remotely or cached and then return a path?!? Okay? sure.
def extract_pudl_table(table_name: str, version="nightly") -> pl.LazyFrame:
    """Read a PUDL table from aws for a given version."""
    return pl.read_parquet(
        f"s3://pudl.catalyst.coop/{version}/{table_name}.parquet",
        storage_options={"aws_region": "us-west-2", "aws_skip_signature": "True"},
    )


include: "electricity_market_model.smk"
