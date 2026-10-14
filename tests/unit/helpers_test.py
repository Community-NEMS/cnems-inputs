"""Test helper functions."""

import json
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import pytest

from cnems_inputs.helpers import load, versioned_r2_uri


@pytest.fixture
def toy_datapackage(tmpdir):
    """A datapackage with columns of types we care about."""
    datapackage_path = Path(tmpdir) / "datapackage.json"
    datapackage_path.write_text(
        json.dumps(
            {
                "resources": [
                    {
                        "name": "test",
                        "schema": {
                            "fields": [
                                {
                                    "name": "int_col",
                                    "type": "integer",
                                },
                                {
                                    "name": "num_col",
                                    "type": "number",
                                },
                                {
                                    "name": "str_col",
                                    "type": "string",
                                },
                            ],
                        },
                    },
                ],
            }
        )
    )
    return datapackage_path


@pytest.fixture
def compliant_df():
    return pd.DataFrame(
        {
            "int_col": [0],
            "num_col": [0.1],
            "str_col": ["hi"],
        }
    )


def test_versioned_r2_uri_env_override(monkeypatch):
    monkeypatch.setenv("CNEMS_INPUT_VERSION_ID", "vTest")
    assert versioned_r2_uri("test", "test_path.csv") == "s3://test/vTest/test_path.csv"


def test_versioned_r2_uri_defaults_to_nightly(monkeypatch):
    monkeypatch.delenv("CNEMS_INPUT_VERSION_ID", raising=False)
    assert (
        versioned_r2_uri("test", "test_path.csv") == "s3://test/nightly/test_path.csv"
    )


def test_load_check_schema(toy_datapackage, compliant_df, tmpdir):
    out_path = Path(tmpdir) / "check_schema.csv"
    load(compliant_df, out_path, toy_datapackage, "test")
    assert out_path.exists()


@pytest.mark.parametrize(
    "column,invalid_value,seek_text",
    [
        ("bogus_col", "bad", "'bogus_col' not in DataFrameSchema"),
        ("int_col", "bad", "Error while coercing 'int_col' to type int64"),
        ("num_col", "bad", "Error while coercing 'num_col' to type float64"),
        # note: everything is coerceable to string so we can't really check str_col
    ],
)
def test_load_check_schema_invalid(
    toy_datapackage, compliant_df, tmpdir, column, invalid_value, seek_text
):
    out_path = Path(tmpdir) / "check_schema.csv"
    noncompliant_df = compliant_df.assign(**{column: [invalid_value]})

    with pytest.raises(pa.errors.SchemaErrors) as excinfo:
        load(noncompliant_df, out_path, toy_datapackage, "test")
    assert seek_text in str(excinfo.value)
