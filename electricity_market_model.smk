configfile: "config/emm_inputs.yaml"

# We want to ensure that all of the files enumerated in the datapackage are definitely
# in the outputs, so look through the datapackage to build up the list of outputs we
# want the snakemake dag to build.
rule emm_inputs:
  input:
    [r2(p) for p in get_published_paths("datapackage.json")],
    r2("datapackage.json"),
    # For validation purposes!
    r2(f"raw/bluesky/supply_curve.csv")

pudl_tables = [
  "out_eia930__hourly_operations",
  "core_eia__codes_balancing_authorities",
  "core_eia861__yearly_balancing_authority",
  "out_eia861__yearly_balancing_authority_service_territory",
  "out_eia__yearly_generators",
]
for pudl_table in pudl_tables:
  rule:
    name: f"raw__pudl__{pudl_table}"
    input: pudl(config["core_supply_curve"]["pudl_version"], pudl_table)
    output: r2(f"raw/pudl/{pudl_table}.parquet")
    shell: "cp {input} {output}"

rule core__base_load__county:
  input:
    out_eia930__hourly_operations_path=r2("raw/pudl/out_eia930__hourly_operations.parquet"),
    core_eia__codes_balancing_authorities_path=r2("raw/pudl/core_eia__codes_balancing_authorities.parquet"),
    core_eia861__yearly_balancing_authority_path=r2("raw/pudl/core_eia861__yearly_balancing_authority.parquet"),
    out_eia861__yearly_balancing_authority_service_territory_path=r2("raw/pudl/out_eia861__yearly_balancing_authority_service_territory.parquet"),
  output: r2("core/base_load__county.csv"),
  params:
    settings=config["base_load"]
  script:
    "src/cnems_inputs/core__base_load__county.py"

rule out__base_load__region:
  input:
    out_eia930__hourly_operations_path=r2("raw/pudl/out_eia930__hourly_operations.parquet"),
    core_eia861__yearly_balancing_authority_path=r2("raw/pudl/core_eia861__yearly_balancing_authority.parquet"),
    out_eia861__yearly_balancing_authority_service_territory_path=r2("raw/pudl/out_eia861__yearly_balancing_authority_service_territory.parquet"),
  output: r2("out/base_load.csv")
  script:
    "src/cnems_inputs/out__base_load__region.py"


rule core__supply_curve__county:
  input:
    out_eia__yearly_generators_path=r2("raw/pudl/out_eia__yearly_generators.parquet"),
    crosswalk_tech_path=r2(f"raw/bluesky/crosswalk_tech.csv"),
    crosswalk_status_path=r2(f"raw/bluesky/crosswalk_status.csv"),
    crosswalk_region_path=r2(f"raw/bluesky/crosswalk_region.csv"),
    crosswalk_steps_path=r2(f"raw/bluesky/crosswalk_steps.csv"),
    dg_path=r2(f"raw/bluesky/dgpv_cap.csv"),
    pop_path=r2(f"raw/bluesky/population.csv"),
  output: r2("core/supply_curve__county.csv"),
  params:
    settings = config["core_supply_curve"]
  script:
    "src/cnems_inputs/core__supply_curve__county.py"


rule out__supply_curve__region:
  input:
    supply_curve_county_path=r2("core/supply_curve__county.csv"),
    crosswalk_steps_path=r2(f"raw/bluesky/crosswalk_steps.csv"),
    crosswalk_region_path=r2(f"raw/bluesky/crosswalk_region.csv"),
  output:
    r2("out/supply_curve.csv")
  params:
    settings = config["core_supply_curve"]
  script:
    "src/cnems_inputs/out__supply_curve__region.py"


rule datapackage:
  input: "datapackage.json"
  output: r2("datapackage.json")
  shell: "cp {input} {output}"

for resource_name in config["core_snapshots"]:
    rule:
        name: f"out__{resource_name}"
        input:
            # NOTE 2026-10-02: eventually we might want to have some helper
            # manage these raw/core/etc. paths
            r2(f"raw/bluesky/{resource_name}.csv"),
            "datapackage.json"
        output:
            r2(f"out/{resource_name}.csv")
        params:
            resource_name=resource_name
        script:
            "src/cnems_inputs/out__emm_inputs.py"


# Make individual rules for each of the bluesky raw snapshots
#
# This allows the integration/conftest materialize function to request only one file from the the archive, so we can only add the files we need
for resource_name, resource_path in config["raw_bluesky"].items():
    rule:
        name: f"raw__{resource_name}"
        input:
            resolve_dataset("eiabluesky", "eiabluesky-v1-1.zip")
        output:
            r2(f"raw/bluesky/{resource_name}.csv")
        params:
            resource_path=resource_path
        script:
          "src/cnems_inputs/raw__emm_inputs.py"
