configfile: "config/emm_inputs.yaml"

EMM_INPUTS = config["emm_inputs"]
# Every time we make a new pipeline to fully build one of these inputs,
# add it into this list
EMM_PROCESSED_INPUTS = ["supply_curve"]
EMM_UNPROCESSED_INPUTS = {
    name: path for (name, path) in EMM_INPUTS.items() if name not in EMM_PROCESSED_INPUTS
}

rule emm_inputs:
  input:
    [storage.r2(versioned_r2_uri(OUTPUT_BUCKET, f"{name}.csv")) for name in EMM_INPUTS],
    storage.r2(versioned_r2_uri(OUTPUT_BUCKET, "datapackage.json"))

wildcard_constraints:
  unprocessed_resource = "|".join(EMM_UNPROCESSED_INPUTS)

rule extract_from_zip:
  input:
    resolve_dataset("eiabluesky", "eiabluesky-v1-1.zip")
  output:
    storage.r2(versioned_r2_uri(OUTPUT_BUCKET, "{unprocessed_resource}.csv"))
  params:
    # could restrict wildcard to regex to avoid specific
    resource_path = lambda wildcards: EMM_UNPROCESSED_INPUTS[wildcards.unprocessed_resource]
  script:
    "src/cnems_inputs/stub_emm_inputs.py"

rule supply_curve:
  input:
    resolve_dataset("eiabluesky", "eiabluesky-v1-1.zip")
  output:
    storage.r2(versioned_r2_uri(OUTPUT_BUCKET, "supply_curve.csv"))
  params:
    pudl_table_name = "out_eia__yearly_generators",
    cwt_path = "sample/electricity_data_pipeline/input/cw_tech.csv",
    cwc_path = "sample/electricity_data_pipeline/input/cw_county.csv",
    cws_path = "sample/electricity_data_pipeline/input/cw_status.csv",
    index_path = "sample/electricity_data_pipeline/input/cw_r.csv",
    cwst_path = "sample/electricity_data_pipeline/input/cw_steps.csv",
    cw_path = "sample/electricity_data_pipeline/input/cw_r.csv",
    dg_path = "sample/electricity_data_pipeline/input/dgpv_cap.csv",
    pop_path = "sample/electricity_data_pipeline/input/County_Population_2010-2022.csv",
    settings = config["supply_curve_config"]
  script:
    "src/cnems_inputs/supply_curve.py"

rule datapackage:
  input: "datapackage.json"
  output: storage.r2(versioned_r2_uri(OUTPUT_BUCKET, "datapackage.json"))
  shell: "cp {input} {output}"
