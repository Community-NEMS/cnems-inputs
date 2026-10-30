import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from cnems_inputs.out__emm_inputs import remap_stubs
from cnems_inputs.raw__emm_inputs import extract


def test_extract_emm_inputs(tmp_path: Path) -> None:
    """Test the EMM extraction method by attempting it with a small sample.

    Ensure that the extraction is run, that it put the output in the place we told it to go
    and that the contents of that extracted output are unchanged.
    """
    archive_path = tmp_path / "inputs.zip"
    resource_path = "input/electricity/cem_inputs/SupplyCurve.csv"
    content = b"region,tech\n1,2\n"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr(resource_path, content)

    output_path = tmp_path / "raw/bluesky/available_capacity.csv"
    extract(
        str(archive_path),
        str(output_path),
        resource_path,
    )

    assert output_path.read_bytes() == content


@pytest.fixture(scope="module")
def toy_datapackage(tmp_path_factory):
    """A datapackage with one resource, tech."""
    datapackage_path = tmp_path_factory.mktemp(__name__) / "datapackage.json"
    datapackage_path.write_text(
        json.dumps(
            {
                "resources": [
                    {
                        "name": "tech",  # remap_stubs will only do R-style boolean parsing for the tech resource
                        "schema": {
                            "fields": [
                                {
                                    "name": "out",
                                    "type": "integer",
                                },
                                {
                                    "name": "flag",
                                    "type": "boolean",
                                },
                                {
                                    "name": "missing",
                                    "type": "string",
                                },
                                {
                                    "name": "untouched",
                                    "type": "integer",
                                },
                            ],
                        },
                    },
                ],
            }
        )
    )
    return datapackage_path


def test_remap_stubs(mocker, toy_datapackage):
    """Ensure column names are getting remapped properly in the stub pipeline.

    Covers:
    - Rename
    - Type coercion
    - Column order
    - Missing columns
    """
    mocker.patch(
        # replace mapping file with a stub for testing
        "cnems_inputs.out__emm_inputs.pd.read_csv",
        return_value=pd.DataFrame(
            {
                "resource_name": ["tech"],
                "column_raw": ["raw"],
                "column_out": ["out"],
                "unit_factor": 2,
            }
        ),
    )
    actual = remap_stubs(
        pd.DataFrame({"raw": [1], "untouched": [3], "flag": ["T_flag"]}),
        "tech",  # remap_stubs will only do R-style boolean parsing for the tech resource
        toy_datapackage,
    )
    pd.testing.assert_frame_equal(
        actual,
        pd.DataFrame(
            {
                "out": [2],
                "flag": pd.Series(
                    [True], dtype="boolean"
                ),  # default is bool but bool is not nullable
                "missing": pd.Series([None], dtype="str"),
                "untouched": [3],
            }
        ),
    )
