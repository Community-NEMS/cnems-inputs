configfile: "config/emm_inputs.yaml"

# We want to ensure that all of the files enumerated in the datapackage are definitely
# in the outputs, so look through the datapackage to build up the list of outputs we
# want the snakemake dag to build.
rule emm_inputs:
  input:
    [r2(p) for p in get_published_paths("datapackage.json")],
    r2("datapackage.json"),
    # For validation purposes!
    r2(f"raw/bluesky/available_capacity.csv")

rule raw__pudl_generators:
  input:
    pudl(config["core_available_capacity"]["pudl_version"], "out_eia__yearly_generators")
  output:
    r2("raw/pudl/out_eia__yearly_generators.parquet"),
  shell: "cp {input} {output}"

rule core__available_capacity__county:
  input:
    out_eia__yearly_generators_path=r2("raw/pudl/out_eia__yearly_generators.parquet"),
    crosswalk_tech_path=r2(f"raw/bluesky/crosswalk_tech.csv"),
    crosswalk_status_path=r2(f"raw/bluesky/crosswalk_status.csv"),
    crosswalk_region_path=r2(f"raw/bluesky/crosswalk_region.csv"),
    crosswalk_steps_path=r2(f"raw/bluesky/crosswalk_steps.csv"),
    dg_path=r2(f"raw/bluesky/dgpv_cap.csv"),
    pop_path=r2(f"raw/bluesky/population.csv"),
  output: r2("core/available_capacity__county.csv"),
  params:
    settings = config["core_available_capacity"]
  script:
    "src/cnems_inputs/core__available_capacity__county.py"


rule out__available_capacity__region:
  input:
    available_capacity_county_path=r2("core/available_capacity__county.csv"),
    crosswalk_steps_path=r2(f"raw/bluesky/crosswalk_steps.csv"),
    crosswalk_region_path=r2(f"raw/bluesky/crosswalk_region.csv"),
  output:
    r2(get_published_path_for_resource("datapackage.json", "available_capacity"))
  params:
    settings = config["core_available_capacity"]
  script:
    "src/cnems_inputs/out__available_capacity__region.py"

rule out__region:
  input: "src/cnems_inputs/properties/region.csv"
  output: r2(get_published_path_for_resource("datapackage.json", "region"))
  shell: "cp {input} {output}"

rule datapackage:
  input: "datapackage.json"
  output: r2("datapackage.json")
  shell: "cp {input} {output}"

# this iterator is super gross but it gives us much more readable yaml for storing a pair of values
for resource_name, subtype in (next(iter(resource.items())) for resource in config["core_snapshots"]):
    rule:
        name: f"out__{resource_name}"
        input:
            # NOTE 2026-10-02: eventually we might want to have some helper
            # manage these raw/core/etc. paths
            r2(f"raw/bluesky/{resource_name}.csv"),
            "datapackage.json"
        output:
            r2(f"out/{subtype}/{resource_name}.csv")
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
