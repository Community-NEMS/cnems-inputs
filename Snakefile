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

EMM_INPUTS = {
    "base_elec_price": "input/residential/BaseElecPrice.csv",
    "base_load": "input/residential/BaseLoad.csv",
    "battery_efficiency": "input/electricity/cem_inputs/BatteryEfficiency.csv",
    "cap_cost": "input/electricity/cem_inputs/CapCost.csv",
    "cap_cost_initial": "input/electricity/cem_inputs/CapCostInitial.csv",
    "cap_factor_vre": "input/electricity/cem_inputs/CapFactorVRE.csv",
    "enduse_base_shares": "input/residential/EnduseBaseShares.csv",
    "enduse_scalar": "input/residential/EnduseScalar.csv",
    "enduse_shapes": "input/residential/EnduseShapes.csv",
    "fom_cost": "input/electricity/cem_inputs/FOMCost.csv",
    "h2_price": "input/electricity/cem_inputs/H2Price.csv",
    "hours_to_buy": "input/electricity/cem_inputs/HourstoBuy.csv",
    "hydro_cap_factor": "input/electricity/cem_inputs/HydroCapFactor.csv",
    "learning_rate": "input/electricity/cem_inputs/LearningRate.csv",
    "load_scalar": "input/residential/LoadScalar.csv",
    "ramp_down_cost": "input/electricity/cem_inputs/RampDownCost.csv",
    "ramp_rate": "input/electricity/cem_inputs/RampRate.csv",
    "ramp_up_cost": "input/electricity/cem_inputs/RampUpCost.csv",
    "reg_reserves_cost": "input/electricity/cem_inputs/RegReservesCost.csv",
    "reserve_margin": "input/electricity/cem_inputs/ReserveMargin.csv",
    "res_tech_upper_bound": "input/electricity/cem_inputs/ResTechUpperBound.csv",
    "supply_curve": "input/electricity/cem_inputs/SupplyCurve.csv",
    "supply_curve_learning": "input/electricity/cem_inputs/SupplyCurveLearning.csv",
    "supply_price": "input/electricity/cem_inputs/SupplyPrice.csv",
    "test_prices": "input/residential/testPrices.csv",
    "tran_cost": "input/electricity/cem_inputs/TranCost.csv",
    "tran_cost_int": "input/electricity/cem_inputs/TranCostInt.csv",
    "tran_limit": "input/electricity/cem_inputs/TranLimit.csv",
    "tran_limit_cap_int": "input/electricity/cem_inputs/TranLimitCapInt.csv",
    "tran_limit_gen_int": "input/electricity/cem_inputs/TranLimitGenInt.csv",
}

rule emm_inputs:
  input: [storage.r2(f"s3://test-catalyst-coop/{name}.csv") for name in EMM_INPUTS]


rule extract_from_zip:
  input:
    resolve_dataset("eiabluesky", "eiabluesky-v1-1.zip")
  output:
    storage.r2("s3://test-catalyst-coop/{resource}.csv")
  params:
    member_path=lambda wildcards: EMM_INPUTS[wildcards.resource]
  script:
    "src/cnems_inputs/stub_supply_curve.py"
