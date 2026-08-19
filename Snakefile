envvars:
  "CLOUDFLARE_R2_ENDPOINT",
  "CLOUDFLARE_R2_ACCESS_KEY_ID",
  "CLOUDFLARE_R2_SECRET_ACCESS_KEY",

storage http:
  provider="http",
  retrieve=False

storage r2:
  provider="s3",
  endpoint_url=os.environ["CLOUDFLARE_R2_ENDPOINT"],
  access_key=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
  secret_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"]

def datastore_resources(dataset, **filters):
    from cnems_inputs.datastore import Datastore
    from pathlib import Path
    local_cache_path = Path("./snakemake/storage/datastore")
    local_cache_path.mkdir(parents=True, exist_ok=True)
    ds = Datastore(local_cache_path=local_cache_path)
    datapackage_descriptor = ds.get_datapackage_descriptor(dataset)
    resource_names = [key.name for key in datapackage_descriptor.get_resources(**filters)]
    resource_paths = [datapackage_descriptor.get_resource_path(name) for name in resource_names]
    return [storage.http(path) for path in resource_paths]


rule supply_curve:
  input:
    datastore_resources("eiabluesky", release="v1.1")
  output:
    storage.r2(f"s3://test-catalyst-coop/supply_curve.csv")
  script:
    "src/cnems_inputs/stub_supply_curve.py"
