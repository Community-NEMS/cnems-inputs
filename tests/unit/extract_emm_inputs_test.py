from pathlib import Path
from zipfile import ZipFile

from cnems_inputs.extract_emm_inputs import extract


def test_extract_copies_configured_members_unchanged(tmp_path: Path) -> None:
    archive_path = tmp_path / "inputs.zip"
    member = "input/electricity/cem_inputs/SupplyCurve.csv"
    content = b"region,tech\n1,2\n"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr(member, content)

    output_path = tmp_path / "raw/bluesky/SupplyCurve.csv"
    extract(
        str(archive_path),
        {"supply_curve": str(output_path)},
        {"supply_curve": member},
    )

    assert output_path.read_bytes() == content
