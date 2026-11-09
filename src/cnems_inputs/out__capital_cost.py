"""Transformation pipeline for capital_cost.csv.

Build overnight capital cost projection data from NLR ATB.
"""

from logging import getLogger
from pathlib import Path

import pandas as pd
import polars as pl

from cnems_inputs.helpers import load

# TODO: really setup logging #73
# Establish logger
logger = getLogger(__name__)


def validate_atb_settings(capital_costs: pd.DataFrame, settings: dict):
    """Validate selection of ATB model, scenario and cost recovery period."""
    parameter_to_col_map = {
        "model": "model_case_nrelatb",
        "scenario": "scenario_atb",
        "cost_recovery_period": "cost_recovery_period_years",
        "atb_year": "report_year",
    }

    for parameter, column in parameter_to_col_map.items():
        if (param := settings[parameter]) not in capital_costs[column].unique():
            raise ValueError(
                f"Selected {param} that isn't a valid NLR ATB setting: specify from {capital_costs[column].unique()}"
            )

    if agg_method := settings["agg_method"] not in ("min", "max", "mean"):
        raise ValueError(
            f"Selected aggregation method {agg_method} invalid: only min, max and mean are valid options."
        )


def transform_capital_cost(
    core_nlratb__yearly_projected_cost_performance: pl.DataFrame,
    crosswalk_tech_lf: pl.LazyFrame,
    crosswalk_steps_lf: pl.LazyFrame,
    crosswalk_region_lf: pl.LazyFrame,
    crosswalk_eia_nlr_tech_types_lf: pl.LazyFrame,
    settings: dict,
) -> pd.DataFrame:
    """Build the capital cost output."""
    # Load data and convert to pandas
    capital_costs = core_nlratb__yearly_projected_cost_performance.to_pandas()
    crosswalk_tech = crosswalk_tech_lf.collect().to_pandas()

    # Load crosswalks
    nlr_eia_tech_crosswalk = crosswalk_eia_nlr_tech_types_lf.collect().to_pandas()
    # Check year of crosswalk matches year of ATB data used
    # TODO: Could eventually have multi-year crosswalk with one mapping per
    # year of ATB data, but this presumes one static map corresponding to one year.
    assert (
        nlr_eia_tech_crosswalk.nlr_atb_year.unique() == settings["atb_year"]
    ).all(), (
        "EIA-NLR ATB crosswalk mapped to years of ATB data not contained in the settings file."
    )

    full_tech_crosswalk = crosswalk_tech.merge(
        nlr_eia_tech_crosswalk, left_on="Technology", right_on="eia_technology_type"
    ).drop(columns="Technology")
    crosswalk_steps = crosswalk_steps_lf.collect().to_pandas()
    crosswalk_region = crosswalk_region_lf.collect().to_pandas()

    validate_atb_settings(capital_costs, settings)  # Check ATB settings are valid
    capital_costs = (
        capital_costs.loc[
            (capital_costs.model_case_nrelatb == settings["model"])
            & (capital_costs.scenario_atb == settings["scenario"])
            & (capital_costs.report_year == settings["atb_year"])
            & (
                capital_costs.cost_recovery_period_years
                == settings["cost_recovery_period"]
            ),
            [
                "projection_year",
                "technology_description",
                "technology_description_detail_1",
                "technology_description_detail_2",
                "capex_overnight_per_kw",
            ],
        ]
    ).drop_duplicates()
    # Filter year to start at model start year and end at model end year
    capital_costs = capital_costs.loc[
        (capital_costs.projection_year >= settings["first_year"])
        & (capital_costs.projection_year <= settings["last_year"])
    ]
    # Check capital costs cover expected range of dates - TODO - make a validation test instead
    assert (capital_costs.projection_year.min() == settings["first_year"]) and (
        capital_costs.projection_year.max() == settings["last_year"]
    )
    # Convert $/kw to $/mw
    capital_costs["capital_cost_usd_per_mw"] = (
        capital_costs["capex_overnight_per_kw"] * 1000
    )
    capital_costs = capital_costs.drop(columns="capex_overnight_per_kw")

    # Sanity check the crosswalk
    # Pairs of NLR tech and tech details should be in the tech crosswalk and in the NLR ATB data, to avoid accidental misentry.
    assert (
        full_tech_crosswalk["nlr_atb_technology_type"]
        .dropna()
        .isin(capital_costs["technology_description"])
        .all()
    ), (
        "Technology descriptors in the EIA-NLR technology crosswalk don't exist in the observed NLR ATB data. Review the mapping spreadsheet."
    )
    assert (
        pd.MultiIndex.from_frame(
            full_tech_crosswalk[
                ["nlr_atb_technology_type", "nlr_atb_technology_type_detailed"]
            ].dropna(how="any")
        )
        .isin(
            pd.MultiIndex.from_frame(
                capital_costs[
                    ["technology_description", "technology_description_detail_1"]
                ]
            )
        )
        .all()
    ), (
        "Detailed technology descriptors in the EIA-NLR technology crosswalk don't exist in the observed NLR ATB data. Review the mapping spreadsheet."
    )

    # Map tech to existing technologies
    cap_cost_df = capital_costs.merge(
        full_tech_crosswalk,
        left_on="technology_description",
        right_on="nlr_atb_technology_type",
        how="inner",  # Drop any technologies not mapped to an EIA type or in the crosswalk
        validate="m:m",
    )

    # If sub-tech types are specified, they should match between the NLR ATB versions.
    cap_cost_df = cap_cost_df.loc[
        (
            cap_cost_df.technology_description_detail_1
            == cap_cost_df.nlr_atb_technology_type_detailed
        )
        | (cap_cost_df.nlr_atb_technology_type_detailed.isna())
        | (cap_cost_df.technology_description_detail_1.isna())
    ]

    # Backfill nuclear costs.
    # NLR ATB doesn't provide nuclear costs until 2030, so where we have nuclear
    # technologies we backfill these values.
    nuclear_mask = cap_cost_df["nlr_atb_technology_type"].eq("Nuclear")

    if nuclear_mask.any():
        backfill_mask = nuclear_mask & cap_cost_df["projection_year"].le(2030)

        assert (
            cap_cost_df.loc[
                backfill_mask & cap_cost_df["projection_year"].ne(2030),
                "capital_cost_usd_per_mw",
            ]
            .isna()
            .all()
        )

        nuclear_costs = (
            cap_cost_df.loc[backfill_mask]
            .sort_values(["tech", "projection_year"])
            .groupby("tech")["capital_cost_usd_per_mw"]
            .bfill()
        )
        cap_cost_df.loc[nuclear_costs.index, "capital_cost_usd_per_mw"] = nuclear_costs

    # After backfill, expect all timestamps and technologies have an associated cost.
    assert cap_cost_df.capital_cost_usd_per_mw.notna().all()

    cap_cost_df = cap_cost_df.drop(
        columns=[
            "technology_description",
            "technology_description_detail_1",
            "technology_description_detail_2",
            "eia_technology_type",
            "nlr_atb_technology_type",
            "nlr_atb_technology_type_detailed",
        ]
    )

    capital_costs = (
        cap_cost_df.groupby(["projection_year", "tech"])
        .agg(settings["agg_method"])
        .round(2)
        .reset_index()
    )
    # Double check we have the expected number of technologies in the end
    # These will be the ones where all detailed technologies attached to numbered inputs in the model are not mapped
    # to any NLR ATB capital costs.
    missing_techs = (
        full_tech_crosswalk["nlr_atb_technology_type"]
        .isna()
        .groupby(full_tech_crosswalk["tech"])
        .all()
    )
    missing_techs = missing_techs[missing_techs].index
    assert set(crosswalk_tech.tech.unique()).difference(
        set(capital_costs.tech.unique())
    ) == set(missing_techs.values), (
        f"Missing technologies that aren't expected to be missing: {set(missing_techs.values)}"
    )

    # Add in region - for each set of capital costs and technologies, apply to every single region.
    capital_df = capital_costs.merge(
        pd.DataFrame({"region": sorted(crosswalk_region.region.unique())}), how="cross"
    )

    # Add in steps. Each technology takes the highest step from the crosswalk.
    step_df = (
        crosswalk_steps.groupby("tech")["step"].max().reset_index()
    )  # Take the last step of each technology
    capital_df = capital_df.merge(step_df, on="tech", how="left", validate="m:1")

    # Final cleanup - sort and reorder columns
    return (
        capital_df.rename(columns={"projection_year": "year"})
        .reindex(
            columns=[
                "region",
                "tech",
                "step",
                "year",
                "capital_cost_usd_per_mw",
                "notes",
            ]
        )
        .sort_values(["tech", "region"])
    )


def transform_capital_cost_initial(capital_cost_df):
    """Create capital cost initial table from full DF by filtering to first year."""
    return (
        capital_cost_df.loc[capital_cost_df.year == capital_cost_df.year.min()]
        .drop(columns="year")
        .rename(columns={"capital_cost_usd_per_mw": "capital_cost_initial_usd_per_mw"})
    )


def run_capital_cost(
    crosswalk_tech_path: str,
    crosswalk_steps_path: str,
    crosswalk_region_path: str,
    core_nlratb__yearly_projected_cost_performance_path: str,
    crosswalk_eia_nlr_tech_types_path: str,
    settings: dict,
    capital_cost_output_path: Path,
    capital_cost_initial_output_path: Path,
    datapackage_path: Path,
):
    """E, T, L."""
    capital_cost = transform_capital_cost(
        core_nlratb__yearly_projected_cost_performance=pl.read_parquet(
            core_nlratb__yearly_projected_cost_performance_path
        ),
        crosswalk_tech_lf=pl.scan_csv(crosswalk_tech_path),
        crosswalk_steps_lf=pl.scan_csv(crosswalk_steps_path),
        crosswalk_region_lf=pl.scan_csv(crosswalk_region_path),
        crosswalk_eia_nlr_tech_types_lf=pl.scan_csv(crosswalk_eia_nlr_tech_types_path),
        settings=settings,
    )
    load(
        capital_cost,
        capital_cost_output_path,
        datapackage_path=datapackage_path,
        resource_name="capital_cost",
    )

    capital_cost_initial = transform_capital_cost_initial(capital_cost)
    load(
        capital_cost_initial,
        capital_cost_initial_output_path,
        datapackage_path=datapackage_path,
        resource_name="capital_cost_initial",
    )


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_capital_cost(
        core_nlratb__yearly_projected_cost_performance_path=snakemake.input[
            "core_nrelatb__yearly_projected_cost_performance_path"
        ],
        crosswalk_tech_path=snakemake.input["crosswalk_tech_path"],
        crosswalk_steps_path=snakemake.input["crosswalk_steps_path"],
        crosswalk_region_path=snakemake.input["crosswalk_region_path"],
        crosswalk_eia_nlr_tech_types_path=snakemake.input[
            "crosswalk_eia_nlr_tech_types_path"
        ],
        settings=snakemake.params["settings"],
        capital_cost_output_path=Path(snakemake.output[0]),
        capital_cost_initial_output_path=Path(snakemake.output[1]),
        datapackage_path=Path(snakemake.input["datapackage_path"]),
    )
