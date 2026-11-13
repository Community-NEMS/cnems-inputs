import datetime as dt

import polars as pl
import pytest

from cnems_inputs.core__base_load__county import validate_base_load_settings


def test_settings_validation():
    good_settings = {
        "eia930_year": 2025,
        "use_pudl_imputed_demand": True,
    }
    out_eia930__hourly_operations = pl.LazyFrame(
        {
            "datetime_utc": [
                dt.datetime(2025, 1, 1, 1, 0, tzinfo=dt.UTC),
                dt.datetime(2025, 1, 1, 2, 0, tzinfo=dt.UTC),
                dt.datetime(2025, 1, 1, 3, 0, tzinfo=dt.UTC),
            ]
        }
    )

    validate_base_load_settings(out_eia930__hourly_operations, good_settings)
    bad_type_settings = {
        "eia930_year": "2025",
        "use_pudl_imputed_demand": True,
    }
    with pytest.raises(TypeError):
        validate_base_load_settings(out_eia930__hourly_operations, bad_type_settings)

    other_bad_type_settings = {
        "eia930_year": 2025,
        "use_pudl_imputed_demand": 1,
    }
    with pytest.raises(TypeError):
        validate_base_load_settings(
            out_eia930__hourly_operations, other_bad_type_settings
        )

    missing_years_settings = {
        "eia930_year": 2030,
        "use_pudl_imputed_demand": False,
    }
    with pytest.raises(AssertionError):
        validate_base_load_settings(
            out_eia930__hourly_operations, missing_years_settings
        )
