from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from snakemake.iocontainers import snakemake


def extract(input_path: Path) -> pl.LazyFrame:
    print(f"reading from {input_path}")
    return pl.scan_csv(input_path)


def transform(raw: pl.LazyFrame) -> pl.LazyFrame:
    return raw


def load(transformed: pl.LazyFrame, output_path: Path) -> None:
    transformed.sink_csv(output_path)


def run(input_path, output_path):
    raw = extract(input_path)
    transformed = transform(raw)
    load(transformed, output_path)


run(snakemake.input[0], snakemake.output[0])
