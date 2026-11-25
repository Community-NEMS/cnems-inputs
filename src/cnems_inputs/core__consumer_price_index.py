"""Early transforms for the BLS CPI data."""

import json
from pathlib import Path

import pandas as pd

from cnems_inputs.helpers import load


def transform_cpi_data(raw_bls_cpi: dict, settings: dict):
    """Grab the annual averaged data from the desired series of CPI data."""
    series = raw_bls_cpi["Results"]["series"]
    df = pd.DataFrame()
    for response in series:
        if response["seriesID"] == settings["series_id"]:
            df = pd.DataFrame(response["data"])
    if df.empty:
        raise ValueError(
            f"{series} doesn't appear to contain any data for {settings['series_id']}."
        )

    annual_df = df.loc[df.periodName == "Annual"]
    annual_df = annual_df.drop(columns=["period", "periodName", "latest"])
    assert not annual_df.empty, "Data is missing."
    return annual_df


def run_cpi_etl(
    raw_bls_cpi_path: str,
    settings: dict,
    cpi_path: Path,
):
    """E, T, L.

    Read in a JSON, grab the annually averaged data, and return it as a CSV.
    """
    with Path(raw_bls_cpi_path).open() as f:
        cpi_df = transform_cpi_data(
            raw_bls_cpi=json.load(f),
            settings=settings,
        )

    load(cpi_df, cpi_path)


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_cpi_etl(
        raw_bls_cpi_path=snakemake.input["raw_bls_cpi_path"],
        settings=snakemake.params["settings"],
        cpi_path=Path(snakemake.output[0]),
    )
