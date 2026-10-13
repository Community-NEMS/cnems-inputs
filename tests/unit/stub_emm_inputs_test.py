from pathlib import Path
from zipfile import ZipFile

import pandas as pd

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

    output_path = tmp_path / "raw/bluesky/supply_curve.csv"
    extract(
        str(archive_path),
        str(output_path),
        resource_path,
    )

    assert output_path.read_bytes() == content


def test_remap_stubs(mocker):
    """Ensure column names are getting remapped properly in the stub pipeline."""
    mocker.patch(
        # replace mapping file with a stub for testing
        "cnems_inputs.out__emm_inputs.pd.read_csv",
        return_value=pd.DataFrame(
            {
                "resource_name": ["test"],
                "column_raw": ["raw"],
                "column_out": ["out"],
            }
        ),
    )
    actual = remap_stubs(
        pd.DataFrame({"raw": [0], "untouched": [1]}),
        "test",
    )
    pd.testing.assert_frame_equal(
        actual,
        pd.DataFrame({"out": [0], "untouched": [1]}),
    )
