"""Early transforms for the base load input."""

from pathlib import Path

import pandas as pd
import polars as pl

from cnems_inputs.helpers import load


def calculate_balancing_authority_population_share_per_county(
    service_territory: pl.DataFrame,
) -> pl.DataFrame:
    """Calculate population-share per county for each Balancing Authority.

    Based on `BlueSky/sample/baseload_data_pipeline/scripts/agg_EMMregions.calc_pop_cw()`
    """
    # calculate regional share (population_share = fraction of the balancing authority population in a given county)
    # calc_pop_cw()
    service_territory_w_balancing_authority_population = (
        service_territory
        # account for multiple regions being assigned to one county, split up pop equally
        .with_columns(
            pl.col("population")
            .len()
            .over(["report_date", "county_id_fips"])
            .alias("county_count")
        )
        .with_columns(
            (pl.col("population") / pl.col("county_count")).alias("population_split")
        )
        # calculate the regional population
        .with_columns(
            pl.col("population_split")
            .sum()
            .over(["report_date", "balancing_authority_code_eia"])
            .alias("population_balancing authority")
        )
        .with_columns(
            (
                pl.col("population_split") / pl.col("population_balancing authority")
            ).alias("population_share")
        )
        .select(
            [
                "report_date",
                "balancing_authority_code_eia",
                "county_id_fips",
                "population_share",
            ]
        )
    )
    return service_territory_w_balancing_authority_population


def transform_base_load_county(
    out_eia930__hourly_operations: pl.DataFrame,
    out_eia930__hourly_subregion_demand: pl.DataFrame,
    settings: dict,
) -> pd.DataFrame:
    """Transform."""
    sm_years = settings["eia930_years"]
    year_filter = pl.col("datetime_utc").dt.year().is_in(sm_years)
    out_eia930__hourly_subregion_demand = out_eia930__hourly_subregion_demand.filter(
        year_filter
    )
    out_eia930__hourly_operations = out_eia930__hourly_operations.filter(year_filter)

    # removes balancing authorities that have sub-regional data from the balancing authority dataset
    bas_from_subregions = out_eia930__hourly_subregion_demand.select(
        pl.col("balancing_authority_code_eia").unique()
    )["balancing_authority_code_eia"].to_list()
    out_eia930__hourly_operations = out_eia930__hourly_operations.filter(
        ~pl.col("balancing_authority_code_eia").is_in(bas_from_subregions)
    )

    all_cols = [
        "datetime_utc",
        "balancing_authority_code_eia",
        "balancing_authority_subregion_code_eia",
        "demand_reported_mwh",
        "demand_imputed_pudl_mwh",
        "demand_imputed_pudl_mwh_imputation_code",
    ]
    ops_cols = [c for c in all_cols if c in out_eia930__hourly_operations]
    return pl.concat(
        [
            out_eia930__hourly_subregion_demand.select(all_cols),
            out_eia930__hourly_operations.select(ops_cols),
        ],
        how="align",
    ).to_pandas()


def run_base_load(
    out_eia930__hourly_subregion_demand_path: str,
    out_eia930__hourly_operations_path: str,
    settings: dict,
    county_output_path: Path,
):
    """E, T, L.

    Attempting to be analogous to: BlueSky/sample/baseload_data_pipeline/outputs/LoadCleaned.csv
    """
    base_load_county = transform_base_load_county(
        out_eia930__hourly_subregion_demand=pl.read_parquet(
            out_eia930__hourly_subregion_demand_path
        ),
        out_eia930__hourly_operations=pl.read_parquet(
            out_eia930__hourly_operations_path
        ),
        settings=settings,
    )

    load(base_load_county, county_output_path)


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_base_load(
        out_eia930__hourly_subregion_demand_path=snakemake.input[
            "out_eia930__hourly_subregion_demand_path"
        ],
        out_eia930__hourly_operations_path=snakemake.input[
            "out_eia930__hourly_operations_path"
        ],
        settings=snakemake.params["settings"],
        county_output_path=Path(snakemake.output[0]),
    )
