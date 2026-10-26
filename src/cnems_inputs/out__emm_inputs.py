"""Transform the EMM input files from the archived input bundle to adhere to the datapackage schema."""

from importlib.resources import as_file, files
from pathlib import Path

import pandas as pd

from cnems_inputs.helpers import load
from cnems_inputs.schema import schema_for


def remap_stubs(
    raw_input_df: pd.DataFrame,
    resource_name: str,
    datapackage_path: Path,
):
    """Remap columns from raw BlueSky sources to datapackage schema."""
    # rename columns
    with as_file(files("cnems_inputs").joinpath("stub_mapping.csv")) as mappings_file:
        mappings = pd.read_csv(mappings_file)
    remap_input = mappings.loc[mappings.resource_name == resource_name]
    if remap_input.empty:
        out_df = raw_input_df
    else:
        out_df = raw_input_df.rename(
            columns={r["column_raw"]: r["column_out"] for r in remap_input.to_records()}
        )
        out_df = out_df.assign(
            **{
                r["column_out"]: (out_df[r["column_out"]] * r["unit_factor"])
                for r in remap_input.to_records()
            }
        )

    # add new columns
    schema = schema_for(datapackage_path, resource_name)
    missing_columns = [c for c in schema.columns if c not in out_df.columns]
    out_df[missing_columns] = pd.NA

    # TODO: False is really not a good boolean default but it'll do for now
    missing_bools = [c for c in missing_columns if schema.dtypes[c].type == "bool"]
    out_df[missing_bools] = False

    # coerce types
    for c, dtype in schema.dtypes.items():
        if dtype.type == "bool" and out_df.dtypes[c] != "bool":
            # R(?) reads T_* as TRUE and empty as FALSE, but dtype.coerce reads empty as TRUE
            out_df[c] = out_df[c].str.startswith("T_")
        out_df[c] = dtype.coerce(out_df[c])

    # correct column order
    return out_df[list(schema.dtypes)]


def run_emm_inputs(
    raw_input_path: Path, output_path: Path, datapackage_path: Path, resource_name: str
):
    """E, T, L."""
    load(
        transformed=remap_stubs(
            raw_input_df=pd.read_csv(raw_input_path),
            resource_name=resource_name,
            datapackage_path=datapackage_path,
        ),
        output_path=output_path,
        datapackage_path=datapackage_path,
        resource_name=resource_name,
    )


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # Snakemake injects this object on execution, ruff doesn't know
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_emm_inputs(
        raw_input_path=Path(snakemake.input[0]),
        output_path=Path(snakemake.output[0]),
        datapackage_path=Path(snakemake.input[1]),
        resource_name=snakemake.params["resource_name"],
    )
