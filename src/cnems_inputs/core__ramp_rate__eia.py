"""Transformation pipeline for ramp_rate__eia.csv.

Build ramp rate estimates by EIA technology based on CEMS and EIA data.
"""

from pathlib import Path

import polars as pl

from cnems_inputs.helpers import load


def transform_ramp_rate_eia(
    out_epacems__yearly_operational_characteristics: pl.LazyFrame,
    core_epa__assn_eia_epacamd: pl.LazyFrame,
    out_eia__yearly_generators: pl.LazyFrame,
) -> pl.LazyFrame:
    """Compute ramp rate per technology from CEMS operational characteristics."""
    return (
        out_epacems__yearly_operational_characteristics.select(
            "report_year",
            "plant_id_eia",
            "emissions_unit_id_epa",
            (pl.col("ramp_up_rate_per_min") * 60).alias("ramp_rate_frac_per_hr"),
        )
        .join(
            core_epa__assn_eia_epacamd.select(
                "report_year", "plant_id_eia", "emissions_unit_id_epa", "generator_id"
            ),
            on=["report_year", "plant_id_eia", "emissions_unit_id_epa"],
        )
        .join(
            out_eia__yearly_generators.select(
                pl.col("report_date").dt.year().alias("report_year"),
                "plant_id_eia",
                "generator_id",
                pl.col("technology_description").alias("technology_description_eia"),
            ),
            on=["report_year", "plant_id_eia", "generator_id"],
        )
        .group_by("technology_description_eia")
        .agg(ramp_rate_frac_per_hr=pl.col("ramp_rate_frac_per_hr").median())
    )


def run_ramp_rate__eia(
    out_epacems__yearly_operational_characteristics_path: str,
    core_epa__assn_eia_epacamd_path: str,
    out_eia__yearly_generators_path: str,
    eia_output_path: Path,
):
    """E, T, L."""
    ramp_rate_eia = transform_ramp_rate_eia(
        out_epacems__yearly_operational_characteristics=pl.scan_parquet(
            out_epacems__yearly_operational_characteristics_path
        ),
        core_epa__assn_eia_epacamd=pl.scan_parquet(core_epa__assn_eia_epacamd_path),
        out_eia__yearly_generators=pl.scan_parquet(out_eia__yearly_generators_path),
    )
    load(ramp_rate_eia.collect().to_pandas(), eia_output_path)


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_ramp_rate__eia(
        # out_epacems__yearly_operational_characteristics_path=snakemake.input[
        #     "out_epacems__yearly_operational_characteristics_path"
        # ],
        # core_epa__assn_eia_epacamd_path=snakemake.input[
        #     "core_epa__assn_eia_epacamd_path"
        # ],
        # out_eia__yearly_generators_path=snakemake.input[
        #     "out_eia__yearly_generators_path"
        # ],
        # settings=snakemake.params["settings"],
        eia_output_path=Path(snakemake.output[0]),
        **snakemake.input,
    )
