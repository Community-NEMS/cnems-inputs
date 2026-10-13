"""Transformation pipeline for capital_cost.csv.

Build overnight capital cost projection data from NREL ATB.
"""

import datetime
from logging import getLogger
from pathlib import Path

import pandas as pd
import polars as pl

from cnems_inputs.helpers import load

# TODO: really setup logging #73
# Establish logger
logger = getLogger(__name__)

def transform_supply_curve_county(
    core_nrelatb__yearly_projected_cost_performance: pl.DataFrame,
    crosswalk_tech_lf: pl.LazyFrame,
    crosswalk_steps_lf: pl.LazyFrame,
    crosswalk_region_lf: pl.LazyFrame,
    settings: dict,
) -> pd.DataFrame:
    """Build the capital cost output.
    """
    # Load data and convert to pandas
    capital_costs = core_nrelatb__yearly_projected_cost_performance.collect().to_pandas()
    crosswalk_tech = crosswalk_tech_lf.collect().to_pandas()
    crosswalk_steps = crosswalk_steps_lf.collect().to_pandas()
    crosswalk_region = crosswalk_region_lf.collect().to_pandas()
    
    # Filter capital cost table to only include selected model.
    if model_selection:=settings['model'] not in capital_costs.model_case_nrelatb:
        raise ValueError(f"Selected {model_selection} that isn't a valid NREL ATB model: specify from {capital_costs.model_case_nrelatb.unique()}")
    capital_costs = capital_costs.loc[capital_costs.model_case_nrelatb == settings['model']]
    
    return capital_costs
    
    
    # # create_supplycurve_cnty -- create an ID column
    # df = eia860m.dropna(subset=["Plant ID"]).copy()
    # df["Plant ID"] = df["Plant ID"].astype(pd.Int64Dtype())
    # df["ID"] = df["Plant ID"].astype(str) + "_" + df["Generator ID"].astype(str)

    # df = pd.merge(df, crosswalk_tech, how="left", on=["Technology"])
    # # all of these do not have a Technology
    # assert (len(missing_tech := df[df.tech.isna()]) < 21) & missing_tech[
    #     missing_tech.Technology.notna()
    # ].empty, (
    #     "We expect to have a small number of records with missing tech value "
    #     f"and all of those should have a null Technology but we found {len(missing_tech)}:"
    #     f"\n\n {missing_tech[['Plant ID', 'Generator ID', 'Technology']]}"
    # )
    # # Check if we are missing too many county fips ids before dropping nulls.

    # missing_fips = df.loc[
    #     df.FIPS_cnty.isna()
    #     & df["Plant State"].notna()
    #     & df["County"].notna()
    #     & (df["County"].str.lower() != "not in file")
    # ]
    # assert missing_fips.empty, (
    #     f"We expect next to no records should not have a fips code and we found {len(missing_fips)}:"
    #     f"\n\n {missing_fips[['PlantID', 'Plant State', 'County']]}"
    # )
    # df = df.dropna(subset=["FIPS_cnty"])
    # df["FIPS_cnty"] = df["FIPS_cnty"].astype(pd.Int64Dtype())

    # # Extract just the code from inside parenthesis within the longer description of
    # # a status. Ex: (OP) Operating
    # crosswalk_status["Status Code"] = crosswalk_status["Status"].str.extract(
    #     r"\((.*?)\)"
    # )
    # df = pd.merge(df, crosswalk_status, how="left", on=["Status Code"]).drop(
    #     columns=["Status Code"]
    # )
    # df = df[df["Keep"] == 1]

    # # create_supplycurve_cnty -- clean up columns
    # drop = [
    #     "Plant ID",
    #     "Generator ID",
    #     "Technology",
    #     "Plant State",
    #     "County",
    #     "Status",
    #     "Keep",
    # ]
    # rename = {
    #     "Net Summer Capacity (MW)": "Capacity",
    #     "Operating Year": "year",
    #     "Planned Retirement Year": "Ret_Year",
    # }
    # df = df.drop(columns=drop).rename(columns=rename)

    # # create_supplycurve_cnty -- keep only online years relevant to the model
    # df.loc[df["year"] < settings["first_year"], "year"] = settings["first_year"]
    # df["year"] = df["year"].astype(pd.Int64Dtype())

    # df.loc[df["year"] > settings["last_year"], "Drop"] = 1
    # df = df[df["Drop"] != 1].drop(columns=["Drop"])

    # # create_supplycurve_cnty -- keep only retirement years relevant to the model
    # df.loc[df["Ret_Year"] == " ", "Ret_Year"] = 9999
    # df.loc[df["Ret_Year"].isna(), "Ret_Year"] = 9999
    # df.loc[df["Ret_Year"] > settings["last_year"], "Ret_Year"] = 9999
    # # move the retirement dates forward to the first_year to cover the case where the
    # # "first_year" is after the timestamp of the data file. Else, retirements that are
    # # between the datafile year and the first year will be missed and we will have
    # # erroneous high capacity.
    # df.loc[
    #     (df["Ret_Year"] < settings["first_year"])
    #     & (df["Ret_Year"] > settings["eia860m_month"].year),
    #     "Ret_Year",
    # ] = settings["first_year"]

    # df["Ret_Year"] = df["Ret_Year"].astype(pd.Int64Dtype())

    # # create_supplycurve_cnty -- remove rows with missing capacity data
    # df.loc[df["Capacity"] == " ", "Capacity"] = 0
    # df.loc[df["Capacity"].isna(), "Capacity"] = 0
    # df["Capacity"] = df["Capacity"].astype(float) / 1000  # fix units

    # # create_supplycurve_cnty -- group data by technology/county/year/retirement year
    # df = df.drop(columns=["ID"])
    # df = df.groupby(by=["tech", "FIPS_cnty", "year", "Ret_Year"], as_index=False).sum()

    # index = pd.merge(
    #     crosswalk_region,
    #     pd.DataFrame(crosswalk_tech["tech"].unique(), columns=["tech"]),
    #     how="cross",
    # )
    # index = pd.merge(
    #     index,
    #     pd.DataFrame(
    #         range(settings["first_year"], settings["last_year"] + 1), columns=["year"]
    #     ),
    #     how="cross",
    # )
    # # create_supplycurve_cnty -- add online capacity for each county/technology/year
    # online = df.drop(columns=["Ret_Year"])
    # online = online.groupby(by=["tech", "FIPS_cnty", "year"], as_index=False).sum()
    # frame = pd.merge(index, online, how="left", on=["FIPS_cnty", "tech", "year"])

    # # create_supplycurve_cnty -- add planned retirement capacity for each county/technology/year
    # offline = df.drop(columns=["year"])
    # offline = offline.groupby(
    #     by=["tech", "FIPS_cnty", "Ret_Year"], as_index=False
    # ).sum()
    # offline = offline.rename(columns={"Capacity": "Ret_Capacity", "Ret_Year": "year"})
    # frame = pd.merge(frame, offline, how="left", on=["FIPS_cnty", "tech", "year"])
    # frame = frame.fillna(0)

    # # create_supplycurve_cnty -- calculate the cumulative sum of the capacities minus retirements
    # frame = frame.set_index(["tech", "FIPS_cnty", "year"])
    # frame["Cap_Cum"] = frame.groupby(by=["tech", "FIPS_cnty"])["Capacity"].cumsum()
    # frame["Ret_Cap_Cum"] = frame.groupby(by=["tech", "FIPS_cnty"])[
    #     "Ret_Capacity"
    # ].cumsum()
    # frame = frame.reset_index()
    # frame = frame[frame["Cap_Cum"] != 0]
    # frame["SupplyCurve"] = frame["Cap_Cum"] - frame["Ret_Cap_Cum"]
    # frame = frame.drop(columns=["Capacity", "Ret_Capacity", "Cap_Cum", "Ret_Cap_Cum"])

    # frame = pd.merge(frame, crosswalk_steps, how="right", on=["tech"]).fillna(0)
    # frame["SupplyCurve"] = (frame["SupplyCurve"] / frame["count"]).apply(
    #     lambda x: round(x, 2)
    # )
    # frame = frame[["FIPS_cnty", "tech", "step", "year", "SupplyCurve"]]
    # frame = frame[frame["year"] > 0]

    # # create_supplycurve_cnty -- add DGPV capacity
    # pop = calc_pop_crosswalk_region(crosswalk_region, pop, settings)

    # dg = sum_data_cnty(dg, pop)
    # frame = pd.concat([frame, dg]).astype(
    #     {
    #         "FIPS_cnty": pd.Int64Dtype(),
    #         "tech": pd.Int64Dtype(),
    #         "step": pd.Int64Dtype(),
    #         "year": pd.Int64Dtype(),
    #         "SupplyCurve": pd.Float64Dtype(),
    #     }
    # )
    # return frame


def run_supply_curve_county(
    crosswalk_tech_path: str,
    crosswalk_status_path: str,
    crosswalk_region_path: str,
    core_nrelatb__yearly_projected_cost_performance_path: str,
    capital_cost_output_path: Path,
):
    """E, T, L."""
    capital_cost = transform_supply_curve_county(
        core_nrelatb__yearly_projected_cost_performance=pl.read_parquet(core_nrelatb__yearly_projected_cost_performance_path),
        crosswalk_tech_lf=pl.scan_csv(crosswalk_tech_path),
        crosswalk_steps_lf=pl.scan_csv(crosswalk_steps_path),
        crosswalk_region_lf=pl.scan_csv(crosswalk_region_path),
        settings=settings,
    )
    load(capital_cost, capital_cost_path)


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_supply_curve_county(
        core_nrelatb__yearly_projected_cost_performance_path=snakemake.input[
            "core_nrelatb__yearly_projected_cost_performance_path"
        ],
        crosswalk_tech_path=snakemake.input["crosswalk_tech_path"],
        crosswalk_steps_path=snakemake.input["crosswalk_steps_path"],
        crosswalk_region_path=snakemake.input["crosswalk_region_path"],
        settings=snakemake.params["settings"],
        capital_cost_path=snakemake.output[0],
    )
