EMM_INPUTS = config["emm_inputs"]

rule emm_inputs:
  input: [storage.r2(f"s3://test-catalyst-coop/{name}.csv") for name in EMM_INPUTS]

rule extract_from_zip:
  input:
    resolve_dataset("eiabluesky", "eiabluesky-v1-1.zip")
  output:
    storage.r2("s3://test-catalyst-coop/{resource}.csv")
  params:
    resource_path=lambda wildcards: EMM_INPUTS[wildcards.resource]
  script:
    "src/cnems_inputs/stub_emm_inputs.py"
