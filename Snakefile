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

def resolve_dataset(dataset, relative_path):
    """Resolve dataset archives through Snakemake's cached HTTP storage."""
    # NOTE (2026-08-26): If we ever use non-Zenodo DOI providers we'll need to
    # dispatch properly.
    return storage.cached_http(resolve(dataset, relative_path))

rule supply_curve:
  input:
    resolve_dataset("eiabluesky", "eiabluesky-v1-1.zip")
  output:
    storage.r2(f"s3://test-catalyst-coop/supply_curve.csv")
  script:
    "src/cnems_inputs/stub_supply_curve.py"
