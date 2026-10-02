configfile: "config/emm_inputs.yaml"

from pathlib import Path

EMM_INPUTS = config["emm_inputs"]

RAW_INPUTS = {
    resource: f"raw/bluesky/{Path(archive_path).name}"
    for resource, archive_path in EMM_INPUTS.items()
}
if len(RAW_INPUTS.values()) != len(set(RAW_INPUTS.values())):
    raise ValueError("EMM input archive paths must have unique basenames")

CORE_OUTPUTS = {
    resource: f"core/{resource}.csv" for resource in EMM_INPUTS
}

rule emm_inputs:
  input:
    [storage.r2(versioned_r2_uri(OUTPUT_BUCKET, path)) for path in CORE_OUTPUTS.values()],
    storage.r2(versioned_r2_uri(OUTPUT_BUCKET, "datapackage.json"))

rule extract_from_zip:
  input:
    resolve_dataset("eiabluesky", "eiabluesky-v1-1.zip")
  output:
    **{
        resource: storage.r2(versioned_r2_uri(OUTPUT_BUCKET, path))
        for resource, path in RAW_INPUTS.items()
    }
  params:
    resource_paths=EMM_INPUTS
  script:
    "src/cnems_inputs/extract_emm_inputs.py"

# Make a rule for each core resource we want to make with generic processing.
#
# NOTE 2026-10-02: Currently that's just a rename.
#
# When we add bespoke processing to an input, add it to the CORE_PRODUCERS set.
CORE_PRODUCERS = set()
for resource, raw_path in RAW_INPUTS.items():
    if resource in CORE_PRODUCERS:
        continue
    rule:
        name: f"core_{resource}"
        input:
            storage.r2(versioned_r2_uri(OUTPUT_BUCKET, raw_path))
        output:
            storage.r2(versioned_r2_uri(OUTPUT_BUCKET, CORE_OUTPUTS[resource]))
        shell:
            "cp {input} {output}"

rule datapackage:
  input: "datapackage.json"
  output: storage.r2(versioned_r2_uri(OUTPUT_BUCKET, "datapackage.json"))
  shell: "cp {input} {output}"
