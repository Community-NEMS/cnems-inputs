"""Early transforms for the base load input."""

from pathlib import Path

import pandas as pd
import polars as pl

from cnems_inputs.helpers import load

STANDARD_UTC_OFFSETS: dict[str, int] = {
    "Pacific/Honolulu": -10,
    "America/Anchorage": -9,
    "America/Los_Angeles": -8,
    "America/Denver": -7,
    "America/Phoenix": -7,
    "America/Chicago": -6,
    "America/New_York": -5,
    "America/Halifax": -4,
}
"""Hour offset from Coordinated Universal Time (UTC) by time zone.

Time zones are canonical names (e.g. 'America/Denver') from tzdata (
https://www.iana.org/time-zones) mapped to their standard-time UTC offset.

Ripped directly from pudl/src/pudl/analysis/timeseries_cleaning.py
"""


def convert_datetime_utc_to_local(
    out_eia930__hourly_operations: pl.DataFrame,
    core_eia__codes_balancing_authorities: pl.DataFrame,
):
    """Convert a UTC datetime to a local datetime by merging timezones with UTC offsets.

    We need to do this because base load output will represent time as with an hour
    column, which is an 8760 representation of a year. So hour 1 should represent hour
    1 in any given region. We also need to select the subset of years to include in
    this output. If we do not change the time to local time before filtering on years,
    we will loose the beginning or ends of the years we are selecting for.

    Instead of relying on `STANDARD_UTC_OFFSETS`, first tried `pl.dt.convert_time_zone`
    but that method only takes one timezone option so it requires looping through each
    timezone AND the real kicker is that polars does not allow multiple different
    timezones within one column.
    """
    # Add UTC offsets to the balancing authorities' timezone's
    balancing_authorities_with_utc_offsets = core_eia__codes_balancing_authorities.join(
        pl.DataFrame(
            data={
                "report_timezone": STANDARD_UTC_OFFSETS.keys(),
                "utc_offset": STANDARD_UTC_OFFSETS.values(),
            },
            schema={"report_timezone": pl.Categorical, "utc_offset": pl.Int64},
        ),
        on="report_timezone",
        how="left",
    )
    out_eia930__hourly_operations = out_eia930__hourly_operations.join(
        balancing_authorities_with_utc_offsets.select(["code", "utc_offset"]),
        left_on="balancing_authority_code_eia",
        right_on="code",
        how="left",
    ).with_columns(
        (pl.col("datetime_utc") + pl.duration(hours="utc_offset")).alias(
            "datetime_local"
        )
    )
    return out_eia930__hourly_operations


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


def convert_datetime_to_hour_of_year(df, datetime_col_name):
    """Add an hour column representing the 8760-hour of the year."""
    return df.with_columns(
        hour=(
            (pl.col(datetime_col_name).dt.ordinal_day() - 1) * 24
            + pl.col(datetime_col_name).dt.hour()
            + 1
        ).cast(pl.Int32)
    )


def transform_base_load_county(
    out_eia930__hourly_operations: pl.DataFrame,
    core_eia__codes_balancing_authorities: pl.DataFrame,
    core_eia861__yearly_balancing_authority: pl.DataFrame,
    out_eia861__yearly_balancing_authority_service_territory: pl.DataFrame,
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
        .pipe(convert_datetime_utc_to_local, core_eia__codes_balancing_authorities)
        .filter(pl.col("datetime_local").dt.year().is_in(eia930_years))
        .join(
            service_territory_w_balancing_authority_population,
            left_on=[
                "balancing_authority_code_eia",
                pl.col("datetime_local").dt.year(),
            ],
            right_on=["balancing_authority_code_eia", pl.col("report_date").dt.year()],
        )
        .with_columns(
            (pl.col(demand_column_name) * pl.col("population_share")).alias(
                "demand_mwh"
            )
        )
        .pipe(convert_datetime_to_hour_of_year, datetime_col_name="datetime_local")
        .group_by(["county_id_fips", "balancing_authority_code_eia", "hour"])
        .agg(pl.col("demand_mwh").sum())
    )

    return base_load_county.to_pandas()


def run_base_load__county(
    out_eia930__hourly_operations_path: str,
    core_eia__codes_balancing_authorities_path: str,
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
        out_eia930__hourly_operations=pl.read_parquet(
            out_eia930__hourly_operations_path
        ),
        core_eia__codes_balancing_authorities=pl.read_parquet(
            core_eia__codes_balancing_authorities_path
        ),
        core_eia861__yearly_balancing_authority=pl.read_parquet(
            core_eia861__yearly_balancing_authority_path
        ),
        out_eia861__yearly_balancing_authority_service_territory=pl.read_parquet(
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
        core_eia__codes_balancing_authorities_path=snakemake.input[
            "core_eia__codes_balancing_authorities_path"
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
