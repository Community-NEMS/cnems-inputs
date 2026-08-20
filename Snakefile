envvars:
  "CLOUDFLARE_R2_ENDPOINT",
  "CLOUDFLARE_R2_ACCESS_KEY_ID",
  "CLOUDFLARE_R2_SECRET_ACCESS_KEY",

storage r2:
  provider="s3",
  endpoint_url=os.environ["CLOUDFLARE_R2_ENDPOINT"],
  access_key=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
  secret_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"]

def datastore_resources(dataset, **filters):
    from cnems_inputs.datastore import Datastore
    from pathlib import Path
    local_cache_path = Path(".snakemake/storage/datastore")
    local_cache_path.mkdir(parents=True, exist_ok=True)
    # NOTE (2026-08-20): if we decide on cloud cache for Datastore, should
    # configure that here too.
    ds = Datastore(local_cache_path=local_cache_path)
    resources = ds.get_resources(dataset, **filters)
    return [local_cache_path / key.get_local_path() for key, _contents in resources]


rule supply_curve:
  input:
    datastore_resources("eiabluesky", release="v1.1")
  output:
    storage.r2(f"s3://test-catalyst-coop/supply_curve.csv")
  script:
    "src/cnems_inputs/stub_supply_curve.py"
