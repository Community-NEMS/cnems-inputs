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

rule supply_curve:
  input: 
    storage.http("https://raw.githubusercontent.com/EIAgov/BlueSky/refs/heads/main/input/electricity/cem_inputs/SupplyCurve.csv")
  output:
    storage.r2(f"s3://test-catalyst-coop/supply_curve.csv")
  script:
    "src/cnems_inputs/stub_supply_curve.py"
