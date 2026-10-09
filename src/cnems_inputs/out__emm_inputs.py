"""Ensure the configured EMM input files adhere to the datapackage schema."""

from pathlib import Path

import pandas as pd

from cnems_inputs.helpers import load

if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # Snakemake injects this object on execution, ruff doesn't know
        from snakemake.iocontainers import snakemake  # noqa: TC004

    load(
        transformed=pd.read_csv(snakemake.input[0]),
        output_path=Path(snakemake.output[0]),
        resource_name=snakemake.params["resource_name"],
    )
