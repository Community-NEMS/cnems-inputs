"""Module for transforming and loading the tech property file."""

from pathlib import Path

import pandas as pd
import polars as pl

from cnems_inputs.helpers import load
from cnems_inputs.out__emm_inputs import remap_stubs


def transform_tech(
    tech: pl.DataFrame, crosswalk_tech: pl.DataFrame, datapackage_path: Path
) -> pd.DataFrame:
    """Alter the tech property file."""
    tech = pl.from_pandas(remap_stubs(tech.to_pandas(), "tech", datapackage_path))
    # grab the tech's that are considered gas-fired based on the EIA
    # technology description.
    # Note: we could use a .str.contains("Natural Gas") of this general filter, but specifically
    # spelling out the technologies is more explicit.
    gas_technologies = [
        "Natural Gas Fired Combined Cycle",
        "Natural Gas Fired Combustion Turbine",
        "Natural Gas Steam Turbine",
        "Natural Gas Internal Combustion Engine",
        "Other Natural GasOther Gases",
        #  Didn't include this guy bc there are
        # 'Natural Gas with Compressed Air Storage'
    ]
    gas_techs = (
        crosswalk_tech.filter(pl.col("Technology").is_in(gas_technologies))
        .get_column("tech")
        .unique()
        .cast(pl.String)
        .to_list()
    )
    return tech.with_columns(
        pl.col("tech").is_in(gas_techs).alias("is_gas_fired")
    ).to_pandas()


def run_tech(
    tech_path: str,
    crosswalk_tech_path: str,
    datapackage_path: Path,
    output_path: Path,
):
    """E, T, L."""
    tech = transform_tech(
        tech=pl.read_csv(tech_path),
        crosswalk_tech=pl.read_csv(crosswalk_tech_path),
        datapackage_path=datapackage_path,
    )
    load(
        tech,
        output_path,
        datapackage_path=datapackage_path,
        resource_name="tech",
    )


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_tech(
        tech_path=snakemake.input["tech_path"],
        crosswalk_tech_path=snakemake.input["crosswalk_tech_path"],
        datapackage_path=Path(snakemake.input["datapackage_path"]),
        output_path=Path(snakemake.output[0]),
    )
