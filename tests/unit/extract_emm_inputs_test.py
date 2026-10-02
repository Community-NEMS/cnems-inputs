from pathlib import Path
from zipfile import ZipFile

from cnems_inputs.extract_emm_inputs import extract


def test_extract_copies_configured_members_unchanged(tmp_path: Path) -> None:
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
