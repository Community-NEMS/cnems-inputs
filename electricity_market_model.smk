configfile: "config/emm_inputs.yaml"

# We want to ensure that all of the files enumerated in the datapackage are definitely
# in the outputs, so look through the datapackage to build up the list of outputs we
# want the snakemake dag to build.
rule emm_inputs:
  input:
    [r2(p) for p in get_published_paths("datapackage.json")],
    r2("datapackage.json")

# TODO: enable grabbing multiple files from config once dazhong changes config into raw/core
rule raw_pudl:
  input: pudl("stable", "out_eia__yearly_generators")
  output: r2("raw/out_eia__yearly_generators.parquet")
  shell: "cp {input} {output}"


# TODO.... Make this work with DX's new raw/core input setup
rule core_supply_curve_county:
  input:
    resolve_dataset("eiabluesky", "eiabluesky-v1-1.zip"),
    r2("raw/out_eia__yearly_generators.parquet"),
    r2(f"raw/bluesky/crosswalk_tech.csv"),
    r2(f"raw/bluesky/crosswalk_county.csv"),
    r2(f"raw/bluesky/crosswalk_status.csv"),
    r2(f"raw/bluesky/crosswalk_region.csv"),
    r2(f"raw/bluesky/crosswalk_steps.csv"),
    r2(f"raw/bluesky/dgpv_cap.csv"),
    r2(f"raw/bluesky/population.csv"),
  output: r2("core/supply_curve_county.csv"),
  params:
    settings = config["core_supply_curve"]
  script:
    "src/cnems_inputs/supply_curve_county.py"


rule core_supply_curve_regional:
  input:
    resolve_dataset("eiabluesky", "eiabluesky-v1-1.zip"),
    r2("core/supply_curve_county.csv")
  output:
    r2("core/supply_curve.csv")
  params:
    cwst_path = "sample/electricity_data_pipeline/input/cw_steps.csv",
    cw_path = "sample/electricity_data_pipeline/input/cw_r.csv",
    settings = config["core_supply_curve"]
  script:
    "src/cnems_inputs/supply_curve_regional.py"


rule datapackage:
  input: "datapackage.json"
  output: r2("datapackage.json")
  shell: "cp {input} {output}"

for resource_name in config["core_snapshots"]:
    rule:
        name: f"core__{resource_name}"
        input:
            # NOTE 2026-10-02: eventually we might want to have some helper
            # manage these raw/core/etc. paths
            r2(f"raw/bluesky/{resource_name}.csv")
        output:
            r2(f"core/{resource_name}.csv")
        shell:
            "cp {input} {output}"


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
          "src/cnems_inputs/extract_emm_inputs.py"
