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
    """Copy configured archive members to their raw output paths unchanged.

    The output and archive-member paths are keyed by resource name so the
    extraction does not depend on dictionary iteration order.  The extraction
    deliberately copies bytes rather than parsing and rewriting CSV files.
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
        # Snakemake injects this object when executing the script.
        from snakemake.iocontainers import snakemake  # noqa: TC004

    extract(
        archive_path=snakemake.input[0],
        output_paths={
            resource: snakemake.output[resource]
            for resource in snakemake.params["resource_paths"]
        },
        resource_paths=snakemake.params["resource_paths"],
    )
