"""Transform the EMM input files from the archived input bundle to adhere to the datapackage schema."""

from importlib.resources import as_file, files
from pathlib import Path

import pandas as pd

from cnems_inputs.helpers import load


def remap_stubs(
    raw_input_df: pd.DataFrame,
    resource_name: str,
):
    """Remap column names from raw BlueSky sources to datapackage schema."""
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
    return out_df


def run_emm_inputs(
    raw_input_path: Path, output_path: Path, datapackage_path: Path, resource_name: str
):
    """E, T, L."""
    load(
        transformed=remap_stubs(
            raw_input_df=pd.read_csv(raw_input_path), resource_name=resource_name
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
