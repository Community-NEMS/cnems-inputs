configfile: "config/emm_inputs.yaml"

# Every time we make a new pipeline to fully build one of these
# inputs, remove that input from this config?
EMM_INPUTS = config["emm_inputs"]
EMM_PROCESSED_INPUTS = ["supply_curve"]
EMM_UNPROCESSED_INPUTS = [i for i in EMM_INPUTS if i not in EMM_PROCESSED_INPUTS]

rule emm_inputs:
  input:
    [storage.r2(versioned_r2_uri(OUTPUT_BUCKET, f"{name}.csv")) for name in EMM_INPUTS],
    storage.r2(versioned_r2_uri(OUTPUT_BUCKET, "datapackage.json"))


wildcard_constraints:
    unprocessed_resource="|".join(EMM_UNPROCESSED_INPUTS)

rule extract_from_zip:
  input:
    resolve_dataset("eiabluesky", "eiabluesky-v1-1.zip")
  output:
    storage.r2(versioned_r2_uri(OUTPUT_BUCKET, "{unprocessed_resource}.csv"))
  params:
    # could restrict wildcard to regex to avoid specific
    resource_path=lambda wildcards: EMM_UNPROCESSED_INPUTS[wildcards.unprocessed_resource]
  script:
    "src/cnems_inputs/stub_emm_inputs.py"


def myfunc(wildcards):
    return


rule supply_curve:
  input:
    {
      "archive_path": resolve_dataset("eiabluesky", "eiabluesky-v1-1.zip"),
      "out_eia__yearly_generators": load_pudl_table(table_name="out_eia__yearly_generators")
    }
  output:
    storage.r2(versioned_r2_uri(OUTPUT_BUCKET, "SupplyCurve.csv"))
  params:
    cwt_path="input/cw_tech.csv",
    cwc_path="input/cwc_path.csv",
    cws_path="input/cws_path.csv",
    indx_path="input/indx_path.csv",
    cwst_path="input/cwst_path.csv",
    cw_path="input/cw_path.csv",
    dg_path="input/dg_path.csv",
    pop_path="input/pop_path.csv",
    settings=config["supply_curve_config"]
  script:
    "src/cnems_inputs/supply_curve.py"

rule datapackage:
  input: "datapackage.json"
  output: storage.r2(versioned_r2_uri(OUTPUT_BUCKET, "datapackage.json"))
  shell: "cp {input} {output}"
