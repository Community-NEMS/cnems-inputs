"""Ensure the configured EMM input files adhere to the datapackage schema."""

from pathlib import Path


def load(
    input_path: str,
    output_path: str,
    resource_name: str,
) -> None:
    """Ensure schema is correct for output paths.

    Args:
        input_path: raw extracted source for this resource
        output_paths: where to write this resource to
        resource_name: name under which schema information is available in datapackage.json
    """
    # get the schema

    # load the file
    # do the changes
    # write the output
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # Snakemake injects this object on execution, ruff doesn't know
        from snakemake.iocontainers import snakemake  # noqa: TC004

    load(
        input_path=snakemake.input[0],
        output_path=snakemake.output[0],
        resource_name=snakemake.params["resource_name"],
    )
