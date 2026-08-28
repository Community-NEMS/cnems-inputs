configfile: "config/emm_inputs.yaml"

EMM_INPUTS = config["emm_inputs"]

rule emm_inputs:
  input: [storage.r2(f"{R2_BASE}/{name}.csv") for name in EMM_INPUTS]

rule extract_from_zip:
  input:
    resolve_dataset("eiabluesky", "eiabluesky-v1-1.zip")
  output:
    storage.r2(f"{R2_BASE}/{{resource}}.csv")
  params:
    resource_path=lambda wildcards: EMM_INPUTS[wildcards.resource]
  script:
    "src/cnems_inputs/stub_emm_inputs.py"
