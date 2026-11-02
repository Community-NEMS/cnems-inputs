"""Test schema functions."""

import json

import pytest

from cnems_inputs.schema import schema_for


@pytest.fixture(scope="module")
def toy_datapackage(tmp_path_factory):
    """A datapackage with two resources, test and not_test."""
    datapackage_path = tmp_path_factory.mktemp(__name__) / "datapackage.json"
    datapackage_path.write_text(
        json.dumps(
            {
                "resources": [
                    {
                        "name": "test",
                        "schema": {
                            "fields": [
                                {
                                    "name": "test_col",
                                    "type": "integer",
                                },
                            ],
                        },
                    },
                    {
                        "name": "not_test",
                        "schema": {
                            "fields": [
                                {
                                    "name": "not_test_col",
                                    "type": "integer",
                                },
                            ],
                        },
                    },
                    {
                        "name": "test_booleans",
                        "schema": {
                            "fields": [
                                {
                                    "name": "bool_col",
                                    "type": "boolean",
                                }
                            ]
                        },
                    },
                ],
            }
        )
    )
    return datapackage_path


def test_schema_for(toy_datapackage):
    """Ensure we get only the table we asked for."""
    actual = schema_for(toy_datapackage, "test")
    assert "test_col" in actual.dtypes
    assert "not_test_col" not in actual.dtypes


def test_schema_for_invalid(toy_datapackage):
    """Ensure we raise when we don't recognize the table."""
    with pytest.raises(ValueError):
        schema_for(toy_datapackage, "unknown_resource")


def test_schema_boolean_dtype(toy_datapackage):
    """Ensure we get a schema with 'boolean' dtype not 'bool'."""
    actual = schema_for(toy_datapackage, "test_booleans")
    assert actual.dtypes["bool_col"].type == "boolean"
