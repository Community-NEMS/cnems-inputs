"""Transformation pipeline for ramp_rate.csv.

Aggregate EIA-level ramp rate estimates by tech.
"""

from pathlib import Path

import polars as pl

from cnems_inputs.helpers import load, merge_tech_label_on_technology_description


def transform_ramp_rate(
    core__ramp_rate__eia: pl.DataFrame,
    crosswalk_tech: pl.DataFrame,
    settings: dict,
) -> pl.DataFrame:
    """Compute ramp-rate-by-tech from ramp-rate-by-EIA-technology."""
    return (
        merge_tech_label_on_technology_description(
            core__ramp_rate__eia.rename(
                {"technology_description_eia": "technology_description"}
            ),
            crosswalk_tech,
        )
        .filter(~pl.col("tech").is_in(settings["exclude_techs"]))
        .drop("technology_description")
        .group_by("tech")
        .agg(
            ramp_rate_frac_per_hr=pl.col(
                "ramp_rate_frac_per_hr"
            ).median()  # hmm this seems bad
        )
        .with_columns(pl.lit("").alias("notes"))
    )


def run_ramp_rate(
    settings: dict,
    core__ramp_rate__eia_path: str,
    crosswalk_tech_path: str,
    ramp_rate_output_path: Path,
    datapackage_path: str,
):
    """E, T, L."""
    ramp_rate = transform_ramp_rate(
        core__ramp_rate__eia=pl.read_csv(core__ramp_rate__eia_path),
        crosswalk_tech=pl.read_csv(crosswalk_tech_path),
        settings=settings,
    )
    load(
        ramp_rate.to_pandas(),
        ramp_rate_output_path,
        Path(datapackage_path),
        "ramp_rate",
    )


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_ramp_rate(
        settings=snakemake.params["settings"],
        ramp_rate_output_path=Path(snakemake.output[0]),
        **snakemake.input,
    )
