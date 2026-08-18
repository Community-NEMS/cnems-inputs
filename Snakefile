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
    import pathlib
    local_cache = pathlib.Path(".snakemake/storage/datastore")
    local_cache.mkdir(parents=True, exist_ok=True)
    ds = Datastore(local_cache_path=local_cache)
    # is there a way to only do the *metadata* here and then actually grab the resource in extract()?
    resources = ds.get_resources(dataset=dataset, **filters)
    return [local_cache / key.get_local_path() for key, _bytes in resources]

rule supply_curve:
  input:
    # right now this has to *download every file* before we even start
    datastore_resources("eiabluesky", release="v1.1"),
  output:
    storage.r2(f"s3://test-catalyst-coop/supply_curve.csv")
  script:
    "src/cnems_inputs/stub_supply_curve.py"
