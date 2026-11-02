"""Early transforms for the base load input."""

from pathlib import Path

import pandas as pd
import polars as pl

from cnems_inputs.helpers import load


def calculate_balancing_authority_population_share_per_county(
    service_territory: pl.LazyFrame,
) -> pl.LazyFrame:
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
            .alias("population_balancing_authority")
        )
        .with_columns(
            (
                pl.col("population_split") / pl.col("population_balancing_authority")
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


def convert_datetime_to_hour_of_year(df: pl.LazyFrame, datetime_col_name: str):
    """Add an hour column representing the 8760-hour of the year."""
    return df.with_columns(
        hour=(
            (pl.col(datetime_col_name).dt.ordinal_day() - 1) * 24
            + pl.col(datetime_col_name).dt.hour()
            + 1
        ).cast(pl.Int32)
    )


def transform_base_load_county(
    out_eia930__hourly_operations: pl.LazyFrame,
    core_eia861__yearly_balancing_authority: pl.LazyFrame,
    out_eia861__yearly_balancing_authority_service_territory: pl.LazyFrame,
    settings: dict,
) -> pd.DataFrame:
    """Transform EIA-930 hourly, balancing authority data into county, 8760-hours data."""
    eia930_years = settings["eia930_years"]
    demand_column_name = (
        "demand_imputed_pudl_mwh"
        if settings["use_pudl_imputed_demand"]
        else "demand_reported_mwh"
    )
    # Prep the service territories. the service territory table does not have
    # a `balancing_authority_code_eia` column, so grab that from the balancing authority
    # table. Then use the county level population data in the service territory table
    # to calculate a population share
    service_territory_w_balancing_authority_population = (
        out_eia861__yearly_balancing_authority_service_territory.join(
            core_eia861__yearly_balancing_authority,
            on=["balancing_authority_id_eia", "report_date"],
            how="left",
        )
        .filter(pl.col("report_date").dt.year().is_in(eia930_years))
        .pipe(calculate_balancing_authority_population_share_per_county)
    )

    # Select only the columns we need, convert to local time and then filter the years
    base_load_county = (
        out_eia930__hourly_operations.select(
            ["datetime_utc", "balancing_authority_code_eia", demand_column_name]
        )
        .filter(pl.col("datetime_utc").dt.year().is_in(eia930_years))
        .join(
            service_territory_w_balancing_authority_population,
            left_on=[
                "balancing_authority_code_eia",
                pl.col("datetime_utc").dt.year(),
            ],
            right_on=["balancing_authority_code_eia", pl.col("report_date").dt.year()],
        )
        .with_columns(
            (pl.col(demand_column_name) * pl.col("population_share")).alias(
                "base_load_mwh"
            )
        )
        .pipe(convert_datetime_to_hour_of_year, datetime_col_name="datetime_utc")
        .group_by(["county_id_fips", "balancing_authority_code_eia", "hour"])
        .agg(pl.col("base_load_mwh").mean())
    )
    return base_load_county.collect().to_pandas()


def run_base_load__county(
    out_eia930__hourly_operations_path: str,
    core_eia861__yearly_balancing_authority_path: str,
    out_eia861__yearly_balancing_authority_service_territory_path: str,
    settings: dict,
    county_output_path: Path,
):
    """E, T, L.

    Attempting to be analogous to: BlueSky/sample/baseload_data_pipeline/outputs/LoadCleaned.csv
    but without the weather normalization. Removing weather normalization obviates the need for
    balancing authority subregions.
    """
    base_load_county = transform_base_load_county(
        out_eia930__hourly_operations=pl.scan_parquet(
            out_eia930__hourly_operations_path
        ),
        core_eia861__yearly_balancing_authority=pl.scan_parquet(
            core_eia861__yearly_balancing_authority_path
        ),
        out_eia861__yearly_balancing_authority_service_territory=pl.scan_parquet(
            out_eia861__yearly_balancing_authority_service_territory_path
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

    run_base_load__county(
        out_eia930__hourly_operations_path=snakemake.input[
            "out_eia930__hourly_operations_path"
        ],
        core_eia861__yearly_balancing_authority_path=snakemake.input[
            "core_eia861__yearly_balancing_authority_path"
        ],
        out_eia861__yearly_balancing_authority_service_territory_path=snakemake.input[
            "out_eia861__yearly_balancing_authority_service_territory_path"
        ],
        settings=snakemake.params["settings"],
        county_output_path=Path(snakemake.output[0]),
    )
