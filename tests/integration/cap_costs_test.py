"""Tests for the capital cost transformation pipeline."""

import polars as pl
import pytest

from cnems_inputs.out__capital_cost import (
    transform_capital_cost,
    transform_capital_cost_initial,
)


@pytest.fixture
def capital_cost_inputs():
    """Build small ATB and crosswalk inputs with deterministic expected output."""
    atb_rows = [
        {
            "model_case_nrelatb": model,
            "scenario_atb": "Moderate",
            "cost_recovery_period_years": 30,
            "report_year": atb_year,
            "projection_year": year,
            "technology_description": "UtilityPV",
            "technology_description_detail_1": None,
            "technology_description_detail_2": None,
            "capex_overnight_per_kw": cost,
        }
        for year in (2023, 2024)
        for model, cost in (("Market", 100), ("Market", 200), ("Other", 999))
        for atb_year in (2023, 2024)
    ]
    return {
        "atb": pl.DataFrame(atb_rows),
        "tech": pl.DataFrame({"Technology": ["Solar PV"], "tech": ["solar"]}).lazy(),
        "steps": pl.DataFrame({"tech": ["solar", "solar"], "step": [1, 3]}).lazy(),
        "regions": pl.DataFrame({"region": ["Z", "A"]}).lazy(),
        "tech_types": pl.DataFrame(
            {
                "eia_technology_type": ["Solar PV"],
                "nlr_atb_technology_type": ["UtilityPV"],
                "nlr_atb_technology_type_detailed": [None],
                "nlr_atb_year": [2024],
            }
        ).lazy(),
        "settings": {
            "model": "Market",
            "scenario": "Moderate",
            "cost_recovery_period": 30,
            "atb_year": 2024,
            "first_year": 2023,
            "last_year": 2024,
            "agg_method": "mean",
        },
    }


def transform(inputs, *, settings=None):
    """Call the transformer with the fixture inputs."""
    return transform_capital_cost(
        core_nlratb__yearly_projected_cost_performance=inputs["atb"],
        crosswalk_tech_lf=inputs["tech"],
        crosswalk_steps_lf=inputs["steps"],
        crosswalk_region_lf=inputs["regions"],
        crosswalk_eia_nlr_tech_types_lf=inputs["tech_types"],
        settings=settings or inputs["settings"],
    )


@pytest.mark.parametrize(
    ("agg_method", "expected_cost"),
    [("min", 100_000), ("mean", 150_000), ("max", 200_000)],
)
def test_transform_capital_cost_aggregates_costs_and_expands_regions(
    capital_cost_inputs, agg_method, expected_cost
):
    """Aggregate ATB sub-records, convert units, and produce every region/year."""
    settings = capital_cost_inputs["settings"] | {"agg_method": agg_method}

    result = transform(capital_cost_inputs, settings=settings)

    assert list(result.columns) == [
        "region",
        "tech",
        "step",
        "year",
        "capital_cost_usd_per_mw",
        "notes",
    ]
    assert len(result) == 4
    assert set(result.region) == {"A", "Z"}
    assert set(result.year) == {2023, 2024}
    assert set(result.tech) == {"solar"}
    assert set(result.step) == {3}
    assert result.capital_cost_usd_per_mw.tolist() == [
        expected_cost,
        expected_cost,
        expected_cost,
        expected_cost,
    ]
    assert result.notes.isna().all()


def test_transform_capital_cost_rejects_unknown_atb_selection(capital_cost_inputs):
    """Fail early when configuration selects a model absent from the source data."""
    settings = capital_cost_inputs["settings"] | {"model": "Unknown"}

    with pytest.raises(ValueError, match="isn't a valid NLR ATB setting"):
        transform(capital_cost_inputs, settings=settings)


def test_transform_capital_cost_initial_keeps_only_first_year(capital_cost_inputs):
    """The initial-cost table contains first-year costs and omits the year field."""
    capital_cost = transform(capital_cost_inputs)

    result = transform_capital_cost_initial(capital_cost)

    assert "year" not in result.columns
    assert "capital_cost_initial_usd_per_mw" in result.columns
    assert "capital_cost_usd_per_mw" not in result.columns
    assert len(result) == 2
    assert set(result.region) == {"A", "Z"}
    assert result.capital_cost_initial_usd_per_mw.tolist() == [150_000, 150_000]


def test_transform_capital_cost_backfills_nuclear_costs(capital_cost_inputs):
    """Nuclear values before 2030 are filled from the first available ATB cost."""
    inputs = capital_cost_inputs.copy()
    inputs["atb"] = pl.DataFrame(
        [
            {
                "model_case_nrelatb": "Market",
                "scenario_atb": "Moderate",
                "cost_recovery_period_years": 30,
                "report_year": 2024,
                "projection_year": year,
                "technology_description": "Nuclear",
                "technology_description_detail_1": None,
                "technology_description_detail_2": None,
                "capex_overnight_per_kw": 500 if year == 2030 else None,
            }
            for year in range(2023, 2031)
        ]
    )
    inputs["tech"] = pl.DataFrame(
        {"Technology": ["Nuclear"], "tech": ["nuclear"]}
    ).lazy()
    inputs["tech_types"] = pl.DataFrame(
        {
            "eia_technology_type": ["Nuclear"],
            "nlr_atb_technology_type": ["Nuclear"],
            "nlr_atb_technology_type_detailed": [None],
            "nlr_atb_year": [2024],
        }
    ).lazy()
    inputs["settings"] = inputs["settings"] | {"last_year": 2030}

    result = transform(inputs)

    assert set(result.year) == set(range(2023, 2031))
    assert set(result.capital_cost_usd_per_mw) == {500_000}
    assert result.capital_cost_usd_per_mw.notna().all()
