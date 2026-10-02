"""Extract the configured EMM input files from the archived input bundle."""

import shutil
from collections.abc import Mapping
from pathlib import Path
from zipfile import ZipFile


def extract(
    archive_path: str,
    output_paths: Mapping[str, str],
    resource_paths: Mapping[str, str],
) -> None:
    """Copy configured archive members to their raw output paths.

    Args:
        archive_path: path... to the archive that contains the files.
        output_paths: in-archive path -> output path mapping.
        resource_paths: resource name -> in-archive path to resource mapping.
    """
    with ZipFile(archive_path) as archive:
        if output_paths.keys() != resource_paths.keys():
            raise ValueError(
                "raw outputs and archive members must have matching resources"
            )
        for resource, resource_path in resource_paths.items():
            output = Path(output_paths[resource])
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
        output_paths={
            resource: snakemake.output[resource]
            for resource in snakemake.params["resource_paths"]
        },
        resource_paths=snakemake.params["resource_paths"],
    )
