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

rule supply_curve:
  input:
    storage.cached_http("https://zenodo.org/records/21629428/files/eiabluesky-v1-1.zip")
  output:
    storage.r2(f"s3://test-catalyst-coop/supply_curve.csv")
  script:
    "src/cnems_inputs/stub_supply_curve.py"
