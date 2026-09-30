"""Stub transformation pipeline for SupplyCurve.csv.

Reads a file from GitHub (soon to be Datastore...), then publishes it to R2.
"""

from datetime import datetime
from logging import getLogger
from pathlib import Path

import pandas as pd
import polars as pl

from cnems_inputs.helpers import extract_from_zip

# Establish logger
logger = getLogger(__name__)


class Settings:
    """Settings for Supply Curve.

    TODO: Is there a more snakemake-y place to do validations of settings?
    I'd like to pydantic this guy but this doesn't seem like the right place to do it.
    """

    first_year = 2023
    last_year = 2050
    population_year = 2022
    eia860m_month = "max"
    # eia860m_month = (
    #     datetime.strptime("2025-01-01", "%Y-%m-%d").astimezone(datetime.timezone.utc).date()
    # )


settings = Settings()


def calc_pop_cw(cw: pd.DataFrame, pop: pd.DataFrame, settings) -> pd.DataFrame:
    """Calculate regional population share.

    Maps user-defined region to county and calculates fraction of user-defined region
    population in each county.

    Args:
        cw: pd.DataFrame
            crosswalk of county and user-defined region
        pop:
        settings: input settings

    Returns:
    -------
    pd.DataFrame
        data frame which contains user-defined region/county mapping and the fraction of the user-defined region population in each county
    """
    # calc_pop_cw -- read in county population for population_year and combine w/ regional crosswalk
    population_year = settings.population_year
    pop = pop[pop["year"] == population_year]
    pop = pop.drop(columns=["year"])
    pop = (
        pd.merge(cw, pop, how="right", on=["FIPS_cnty"]).dropna().reset_index(drop=True)
    )

    # calc_pop_cw -- account for multiple regions being assigned to one county, split up pop equally
    cnty_cnt = (
        pop[["FIPS_cnty", "population"]].copy().rename(columns={"population": "count"})
    )
    cnty_cnt = cnty_cnt.groupby(by=["FIPS_cnty"], as_index=False).count()
    pop = pd.merge(pop, cnty_cnt, how="left", on=["FIPS_cnty"])
    pop["population"] = pop["population"] / pop["count"]
    pop = pop.drop(columns=["count"])
    logger.debug(f"calc_pop_cw: {pop.columns}")

    # calc_pop_cw -- get cw id column name for groupby
    cw_id = list(cw.columns)[-1]
    logger.debug(f"calc_pop_cw: {cw_id}")

    # calc_pop_cw -- calculate the regional population
    reg_pop = pop[[cw_id, "population"]].groupby(by=[cw_id], as_index=False).sum()
    reg_pop = reg_pop.rename(columns={"population": "reg_pop"})
    logger.debug(f"calc_pop_cw: {reg_pop.columns}")

    # calc_pop_cw -- calculate regional share
    pop = pd.merge(pop, reg_pop, how="left", on=[cw_id])
    pop["pop_share"] = pop["population"] / pop["reg_pop"]
    pop = pop.drop(columns=["population", "reg_pop"])

    return pop


def get_names(df: pd.DataFrame, pop: pd.DataFrame):
    """Pull column names: region name, data value name, and groupby names.

    Parameters
    ----------
    df : pd.DataFrame
        data frame containing data by user-defined region
    pop : pd.DataFrame
        data frame containing population by county

    Returns:
    -------
    tuple
       where [0] is type str: user-defined region column name
       where [1] is type str: data column name
       where [2] is type list (or str): column names to group by
    """
    # get col names
    cw_id = next(
        item for item in list(pop.columns) if item not in ["FIPS_cnty", "pop_share"]
    )
    data_id = list(df.columns)[-1]
    groupby_cols = [item for item in list(df.columns) if item not in [cw_id, data_id]]
    logger.debug(f"get_names: {cw_id}")
    logger.debug(f"get_names: {data_id}")

    return cw_id, data_id, groupby_cols


def sum_data_cnty(df: pd.DataFrame, pop: pd.DataFrame):
    """Calculate population-weighted data by county.

    Parameters
    ----------
    df : pd.DataFrame
        data frame containing data by user-defined region
    pop : pd.DataFrame
        data frame containing population by county

    Returns:
    -------
    pd.DataFrame
        data frame containing population-weighted data by county
    """
    # sum_data_cnty -- get col names
    cw_id, data_id, groupby_cols = get_names(df, pop)

    # sum_data_cnty -- merge data with county pop and regional pop data, determine county share
    df = pd.merge(pop, df, how="right", on=[cw_id])
    df[data_id] = df[data_id] * df["pop_share"]

    # sum_data_cnty -- calculate total data for each county
    df = df.drop(columns=[cw_id, "pop_share"])
    df = df.groupby(by=["FIPS_cnty"] + groupby_cols, as_index=False).sum(data_id)
    df["FIPS_cnty"] = df["FIPS_cnty"].astype(pd.Int64Dtype())

    return df


def prep_eia860m(
    out_eia__yearly_generators: pl.DataFrame, eia860m_month: max | datetime
) -> pd.DataFrame:
    """Prep the PUDL table for the C-NEMS.

    Args:
        eia860m_month: If month is max, this will default to grabbing the most recent
            month available.
    """
    month_filter = (
        pl.col("report_date") == pl.col("report_date").max()
        if eia860m_month == "max"
        else pl.col("report_date") == eia860m_month
    )

    eia860m = (
        out_eia__yearly_generators.filter(month_filter)
        .with_columns(
            pl.col("generator_operating_date").dt.year().alias("Operating Year"),
            pl.col("generator_retirement_date")
            .dt.year()
            .alias("Planned Retirement Year"),
        )
        .rename(
            {
                "plant_id_eia": "Plant ID",
                "generator_id": "Generator ID",
                "state": "Plant State",
                "county": "County",
                "summer_capacity_mw": "Net Summer Capacity (MW)",
                "technology_description": "Technology",
                "operational_status_code": "Status Code",
            }
        )
    )
    cols_to_keep = [
        "Plant ID",
        "Generator ID",
        "Plant State",
        "County",
        "Net Summer Capacity (MW)",
        "Technology",
        "Status Code",
        "Operating Year",
        "Planned Retirement Year",
    ]
    eia860m = eia860m[cols_to_keep].to_pandas().convert_dtypes()
    return eia860m


def transform_supply_curve(
    out_eia__yearly_generators: pd.DataFrame,
    cwt: pd.DataFrame,
    cwc: pd.DataFrame,
    cws: pd.DataFrame,
    indx: pd.DataFrame,
    cwst: pd.DataFrame,
    cw: pd.DataFrame,
    dg: pd.DataFrame,
    pop: pd.DataFrame,
    settings: Settings,
) -> pd.DataFrame:
    """Build the supply curve output.

    Built mostly from:
    BlueSky/sample/electricity_data_pipeline/src/runner.py::create_supplycurve_cnty
    """
    eia860m = prep_eia860m(out_eia__yearly_generators, settings.eia860m_month)

    # create_supplycurve_cnty -- create an ID column
    df = eia860m.dropna(subset=["Plant ID"]).copy()
    df["Plant ID"] = df["Plant ID"].astype(pd.Int64Dtype())
    df["ID"] = df["Plant ID"].astype(str) + "_" + df["Generator ID"].astype(str)

    df = pd.merge(df, cwt, how="left", on=["Technology"])

    df = pd.merge(
        df,
        cwc[["State", "County", "FIPS_cnty"]].rename(columns={"State": "Plant State"}),
        how="left",
        on=["Plant State", "County"],
    )
    df = df.dropna(subset=["FIPS_cnty"])
    df["FIPS_cnty"] = df["FIPS_cnty"].astype(pd.Int64Dtype())

    # Exctract just the code from inside parenthesis within the
    cws["Status Code"] = cws["Status"].str.extract(r"\((.*?)\)")
    df = pd.merge(df, cws, how="left", on=["Status Code"]).drop(columns=["Status Code"])
    df = df[df["Keep"] == 1]

    # # create_supplycurve_cnty -- clean up columns
    drop = [
        "Plant ID",
        "Generator ID",
        "Technology",
        "Plant State",
        "County",
        "Status",
        "Keep",
    ]
    rename = {
        "Net Summer Capacity (MW)": "Capacity",
        "Operating Year": "year",
        "Planned Retirement Year": "Ret_Year",
    }
    df = df.drop(columns=drop).rename(columns=rename)

    # # create_supplycurve_cnty -- keep only online years relavent to the model
    df.loc[df["year"] < settings.first_year, "year"] = settings.first_year
    df["year"] = df["year"].astype(pd.Int64Dtype())

    df.loc[df["year"] > settings.last_year, "Drop"] = 1
    df = df[df["Drop"] != 1].drop(columns=["Drop"])

    # create_supplycurve_cnty -- keep only retirement years relavent to the model
    df.loc[df["Ret_Year"] == " ", "Ret_Year"] = 9999
    df.loc[df["Ret_Year"].isna(), "Ret_Year"] = 9999
    df.loc[df["Ret_Year"] > settings.last_year, "Ret_Year"] = 9999
    df["Ret_Year"] = df["Ret_Year"].astype(pd.Int64Dtype())

    # create_supplycurve_cnty -- remove rows with missing capacity data
    df.loc[df["Capacity"] == " ", "Capacity"] = 0
    df.loc[df["Capacity"].isna(), "Capacity"] = 0
    df["Capacity"] = df["Capacity"].astype(float) / 1000

    # create_supplycurve_cnty -- group data by technology/county/year/retirement year
    df = df.drop(columns=["ID"])
    df = df.groupby(by=["tech", "FIPS_cnty", "year", "Ret_Year"], as_index=False).sum()

    indx = pd.merge(
        indx, pd.DataFrame(cwt["tech"].unique(), columns=["tech"]), how="cross"
    )
    indx = pd.merge(
        indx,
        pd.DataFrame(
            range(settings.first_year, settings.last_year + 1), columns=["year"]
        ),
        how="cross",
    )
    # create_supplycurve_cnty -- add online capacity for each county/technology/year
    online = df.drop(columns=["Ret_Year"])
    online = online.groupby(by=["tech", "FIPS_cnty", "year"], as_index=False).sum()
    frame = pd.merge(indx, online, how="left", on=["FIPS_cnty", "tech", "year"])

    # create_supplycurve_cnty -- add planned retirement capacity for each county/technology/year
    offline = df.drop(columns=["year"])
    offline = offline.groupby(
        by=["tech", "FIPS_cnty", "Ret_Year"], as_index=False
    ).sum()
    offline = offline.rename(columns={"Capacity": "Ret_Capacity", "Ret_Year": "year"})
    frame = pd.merge(frame, offline, how="left", on=["FIPS_cnty", "tech", "year"])
    frame = frame.fillna(0)

    # create_supplycurve_cnty -- calculate the cumulative sum of the capacities minus retirements
    frame = frame.set_index(["tech", "FIPS_cnty", "year"])
    frame["Cap_Cum"] = frame.groupby(by=["tech", "FIPS_cnty"])["Capacity"].cumsum()
    frame["Ret_Cap_Cum"] = frame.groupby(by=["tech", "FIPS_cnty"])[
        "Ret_Capacity"
    ].cumsum()
    frame = frame.reset_index()
    frame = frame[frame["Cap_Cum"] != 0]
    frame["SupplyCurve"] = frame["Cap_Cum"] - frame["Ret_Cap_Cum"]
    frame = frame.drop(columns=["Capacity", "Ret_Capacity", "Cap_Cum", "Ret_Cap_Cum"])

    frame = pd.merge(frame, cwst, how="right", on=["tech"]).fillna(0)
    frame["SupplyCurve"] = (frame["SupplyCurve"] / frame["count"]).apply(
        lambda x: round(x, 2)
    )
    frame = frame.drop(columns=["count"])
    frame = frame[["FIPS_cnty", "tech", "step", "year", "SupplyCurve"]]
    frame = frame[frame["year"] > 0]

    # create_supplycurve_cnty -- add DGPV capacity
    pop = calc_pop_cw(cw, pop, settings)

    dg = sum_data_cnty(dg, pop)
    frame = pd.concat([frame, dg]).astype(
        {
            "FIPS_cnty": pd.Int64Dtype(),
            "tech": pd.Int64Dtype(),
            "step": pd.Int64Dtype(),
            "year": pd.Int64Dtype(),
            "SupplyCurve": pd.Float64Dtype(),
        }
    )
    return frame


def load(transformed: pd.DataFrame, output_path: Path) -> None:
    """Write DataFrame to output.

    transformed: the data we want to write out.
    output_path: a path for us to write the data out to, which may then be
        pushed remotely via the storage backend configured for this output.
    """
    transformed.to_csv(output_path, index=False)


def run_supply_curve(
    archive_path: Path,
    output_path: Path,
    cwt_path: Path,
    cwc_path: Path,
    cws_path: Path,
    indx_path: Path,
    cwst_path: Path,
    cw_path: Path,
    dg_path: Path,
    pop_path: Path,
    settings: Settings,
    out_eia__yearly_generators: pl.LazyFrame,
):
    """E, T, L."""
    load(
        transform_supply_curve(
            out_eia__yearly_generators,
            cwt=extract_from_zip(archive_path=archive_path, resource_path=cwt_path),
            cwc=extract_from_zip(archive_path=archive_path, resource_path=cwc_path),
            cws=extract_from_zip(archive_path=archive_path, resource_path=cws_path),
            indx=extract_from_zip(archive_path=archive_path, resource_path=indx_path),
            cwst=extract_from_zip(archive_path=archive_path, resource_path=cwst_path),
            cw=extract_from_zip(archive_path=archive_path, resource_path=cw_path),
            dg=extract_from_zip(archive_path=archive_path, resource_path=dg_path),
            pop=extract_from_zip(archive_path=archive_path, resource_path=pop_path),
            settings=Settings(settings),
        ),
        output_path,
    )


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_supply_curve(
        archive_path=snakemake.input["archive_path"],
        output_path=snakemake.output[0],
        cwt_path=snakemake.params["cwt_path"],
        cwc_path=snakemake.params["cwc_path"],
        cws_path=snakemake.params["cws_path"],
        indx_path=snakemake.params["indx_path"],
        cwst_path=snakemake.params["cwst_path"],
        cw_path=snakemake.params["cw_path"],
        dg_path=snakemake.params["dg_path"],
        pop_path=snakemake.params["pop_path"],
        settings=snakemake.params["settings"],
        out_eia__yearly_generators=snakemake.input["out_eia__yearly_generators"],
    )
