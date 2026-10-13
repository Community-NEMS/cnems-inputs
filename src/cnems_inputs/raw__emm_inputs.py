"""Extract the configured EMM input files from the archived input bundle."""

import shutil
from pathlib import Path
from zipfile import ZipFile


def extract(
    archive_path: str,
    output_path: str,
    resource_path: str,
) -> None:
    """Copy configured archive members to their raw output paths.

    Args:
        archive_path: path... to the archive that contains the files.
        output_paths: where to write this resource to
        resource_paths: in-archive path to resource mapping.
    """
    with ZipFile(archive_path) as archive:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(resource_path) as source, output.open("wb") as target:
            shutil.copyfileobj(source, target)


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # Snakemake injects this object on execution, ruff doesn't know
        from snakemake.iocontainers import snakemake  # noqa: TC004

    extract(
        archive_path=snakemake.input[0],
        output_path=snakemake.output[0],
        resource_path=snakemake.params["resource_path"],
    )
