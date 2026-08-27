envvars:
  "CLOUDFLARE_R2_ENDPOINT",
  "CLOUDFLARE_R2_ACCESS_KEY_ID",
  "CLOUDFLARE_R2_SECRET_ACCESS_KEY",

storage cached_http:
  provider="cached-http",
  cache=".snakemake/storage/cached-http/cache"


storage r2:
  provider="s3",
  endpoint_url=os.environ["CLOUDFLARE_R2_ENDPOINT"],
  access_key=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
  secret_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"]

from cnems_inputs.zenodo import resolve

configfile: "config/emm_inputs.yaml"


def resolve_dataset(dataset: str, resource_path: str) -> str:
    """Resolve a resource within a dataset to its URL.

    The dataset is matched up with its DOI defined in
    src/cnems_inputs/zenodo_dois.yaml.

    We register these URLs with `storage.cached_http` so our transforms can
    just read the resources out of snakemake.input[].

    Most of the actual logic lives in `cnems_inputs.zenodo.resolve` - this just
    provides the glue to `storage.cached_http`.

    Args:
        dataset: Dataset name configured in the DOI map.
        resource_path: Path to desired resource relative to the dataset's
            Zenodo record.
    """
    # NOTE (2026-08-26): If we ever use non-Zenodo DOI providers we'll need to
    # dispatch properly.
    return storage.cached_http(resolve(dataset, resource_path))

include: "electricity_market_model.smk"
