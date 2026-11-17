"""Build the county-level input for hydro_capacity_factor."""

from pathlib import Path

import pandas as pd
import polars as pl

from cnems_inputs.helpers import filter_eia_by_report_date, load


def transform_hydro_capacity_factor_county(
    out_eia__yearly_generators: pl.DataFrame, settings: dict
) -> pd.DataFrame:
    """Build a county level hydro capacity factor."""
    gens = filter_eia_by_report_date(
        out_eia__yearly_generators,
        settings["eia860m_month"],
        # only ever use final data here, bc we need the EIA-923 derived values
        # and in PUDL, only the full yearly data has heat rate calculated.
        data_maturity="final",
    )
    month_to_season = {
        1: "Winter",
        2: "Winter",
        3: "Spring",
        4: "Spring",
        5: "Spring",
        6: "Summer",
        7: "Summer",
        8: "Summer",
        9: "Autumn",
        10: "Autumn",
        11: "Autumn",
        12: "Winter",
    }

    gens = (
        gens
        # make a season column based on the report_date
        .with_columns(
            pl.col("report_date")
            .dt.month()
            .replace_strict(month_to_season)
            .alias("season")
        )
        .filter(pl.col("technology_description").str.contains("Hydroelectric"))
        # actually calculate the cap factor? or use pudl?
        .group_by(["season", "county_id_fips"])
        .agg(
            # weighted average for capacity_factor
            (
                pl.col("capacity_factor").dot(pl.col("capacity_mw"))
                / pl.col("capacity_mw").sum()
            ).alias("capacity_factor")
        )
    )
    return gens.to_pandas()


def run_hydro_capacity_factor__county(
    out_eia__yearly_generators_path: str, settings: dict, county_output_path: Path
):
    """E, T, L.

    Attempting to be analogous to: BlueSky/sample/baseload_data_pipeline/outputs/LoadCleaned.csv
    but without the weather normalization. Removing weather normalization obviates the need for
    balancing authority subregions.
    """
    hydro_capacity_factor_county = transform_hydro_capacity_factor_county(
        out_eia__yearly_generators=pl.read_parquet(out_eia__yearly_generators_path),
        settings=settings,
    )

    load(hydro_capacity_factor_county, county_output_path)


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_hydro_capacity_factor__county(
        out_eia__yearly_generators_path=snakemake.input[
            "out_eia__yearly_generators_path"
        ],
        settings=snakemake.params["settings"],
        county_output_path=Path(snakemake.output[0]),
    )
