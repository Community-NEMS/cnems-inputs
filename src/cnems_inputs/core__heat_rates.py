"""unit_heat_rate_mmbtu_per_mwh from PUDL's out_eia__monthly_generators."""

from pathlib import Path

import pandas as pd
import polars as pl

from cnems_inputs.helpers import (
    filter_eia_by_report_date,
    load,
    merge_tech_label_on_technology_description,
)


def transform_heat_rates(
    out_eia__yearly_generators: pl.DataFrame,
    crosswalk_tech: pl.DataFrame,
    settings: dict,
) -> pd.DataFrame:
    """Grab heat rates from EIA-923 and EIA-860 derived values."""
    gens = filter_eia_by_report_date(
        out_eia__yearly_generators, settings["eia860m_month"]
    ).pipe(merge_tech_label_on_technology_description, crosswalk_tech)

    heat_rates = (
        gens.select(
            [
                "tech",
                "technology_description",
                "unit_id_pudl",
                "net_generation_mwh",
                "unit_heat_rate_mmbtu_per_mwh",
            ]
        )
        .filter(
            pl.col("unit_heat_rate_mmbtu_per_mwh").is_not_null()
            & ~pl.col("unit_heat_rate_mmbtu_per_mwh").is_infinite()
        )
        .group_by(["tech"])
        .agg(
            # we could do a straight mean of the unit heat rates, but a weighted
            # average seems more representative
            (
                pl.col("unit_heat_rate_mmbtu_per_mwh").dot(pl.col("net_generation_mwh"))
                / pl.col("net_generation_mwh").sum()
            ).alias("heat_rate_mmbtu_per_mwh")
        )
        .sort("tech")
        .with_columns(pl.lit(None).cast(pl.String).alias("notes"))
    )

    return heat_rates.to_pandas()


def run_heat_rates(
    out_eia__yearly_generators_path: str,
    crosswalk_tech_path: str,
    settings: dict,
    output_path: Path,
):
    """E, T, L."""
    heat_rates = transform_heat_rates(
        out_eia__yearly_generators=pl.read_parquet(out_eia__yearly_generators_path),
        crosswalk_tech=pl.read_csv(crosswalk_tech_path),
        settings=settings,
    )
    load(heat_rates, output_path)


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # NOTE (2026-08-20): outside of type checking context, the Snakemake
        # runtime injects the `snakemake` object, but ruff doesn't know that
        # so it complains about this import
        from snakemake.iocontainers import snakemake  # noqa: TC004

    run_heat_rates(
        out_eia__yearly_generators_path=snakemake.input[
            "out_eia__yearly_generators_path"
        ],
        crosswalk_tech_path=snakemake.input["crosswalk_tech_path"],
        settings=snakemake.params["settings"],
        output_path=Path(snakemake.output[0]),
    )
