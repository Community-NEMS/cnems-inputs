from pathlib import Path
from zipfile import ZipFile

from cnems_inputs.extract_emm_inputs import extract


def test_extract_emm_imputs(tmp_path: Path) -> None:
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
