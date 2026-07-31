"""CLI for managing raw data inputs to the C-NEMS input data processing pipeline."""

from __future__ import annotations

import pathlib
import sys
from typing import TYPE_CHECKING

import click

from cnems_inputs.datastore import ZenodoDoiSettings

if TYPE_CHECKING:
    from cnems_inputs.datastore import Datastore

_KNOWN_DATASETS = sorted(ZenodoDoiSettings.model_fields)


def _print_partitions(dstore: Datastore, datasets: list[str]) -> None:
    """Print known partition keys and values for each of the datasets."""
    from cnems_inputs.datastore.datastore import ZenodoFetcher

    for single_ds in datasets:
        partitions = dstore.get_datapackage_descriptor(single_ds).get_partitions()

        print(f"\nPartitions for {single_ds} ({ZenodoFetcher().get_doi(single_ds)}):")
        for partition_key in sorted(partitions):
            # try-except required for datasets with parts having heterogenous types,
            # since they can't be sorted: [1, 2, None]
            try:
                parts = sorted(partitions[partition_key])
            except TypeError:
                parts = partitions[partition_key]
            print(f"  {partition_key}: {', '.join(str(x) for x in parts)}")
        if not partitions:
            print("  -- no known partitions --")


def _parse_key_values(
    ctx: click.core.Context,
    param: click.Option,
    values: str,
) -> dict[str, str]:
    """Parse key-value pairs into a Python dictionary.

    Transforms a command line argument of the form: k1=v1,k2=v2,k3=v3...
    into: {k1:v1, k2:v2, k3:v3, ...}
    """
    out_dict = {}
    for val in values:
        for key_value in val.split(","):
            key, value = key_value.split("=")
            out_dict[key] = value
    return out_dict


@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument(
    "datasets",
    nargs=-1,
    type=click.Choice(_KNOWN_DATASETS),
)
@click.option(
    "--all",
    "all_datasets",
    is_flag=True,
    default=False,
    help=(
        "Operate on all known datasets. Mutually exclusive with specifying individual "
        "DATASETS arguments. Useful for automation where maintaining an explicit list "
        "of dataset names would risk getting out of sync with ZenodoDoiSettings."
    ),
)
@click.option(
    "--validate",
    is_flag=True,
    default=False,
    help="Validate the contents of locally cached data, but don't download anything.",
)
@click.option(
    "--list-partitions",
    help="List the available partition keys and values for each specified dataset.",
    is_flag=True,
    default=False,
)
@click.option(
    "--partition",
    "-p",
    multiple=True,
    help=(
        "Only operate on dataset partitions matching these conditions. The argument "
        "should have the form: key1=val1,key2=val2,... Conditions are combined with "
        "a boolean AND, functionally meaning each key can only appear once. "
        "If a key is repeated, only the last value is used. "
        "So state=ca,year=2022 will retrieve all California data for 2022, and "
        "state=ca,year=2021,year=2022 will also retrieve California data for 2022, "
        "while state=ca by itself will retrieve all years of California data."
    ),
    callback=_parse_key_values,
)
@click.option(
    "--bypass-local-cache",
    is_flag=True,
    default=False,
    help=(
        "If enabled, locally cached data will not be used. Instead, a new copy will be "
        "downloaded from Zenodo or the cloud cache if specified."
    ),
)
# TODO: decide if we want cloud caching
# @click.option(
#     "--cloud-cache-path",
#     type=str,
#     default="s3://???/zenodo",
#     help=(
#         "Load cached inputs from cloud object storage (S3 or GCS) . This is typically "
#         "much faster and more reliable than downloading from Zenodo directly. By "
#         "default we read from the cache in C-NEMS's free, public AWS Open Data Registry "
#         "bucket."
#     ),
# )
@click.option(
    "--logfile",
    help="If specified, write logs to this file.",
    type=click.Path(
        exists=False,
        resolve_path=True,
        path_type=pathlib.Path,
    ),
)
@click.option(
    "--loglevel",
    default="INFO",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
)
def main(
    datasets: tuple[str, ...],
    all_datasets: bool,
    validate: bool,
    list_partitions: bool,
    partition: dict[str, int | str],
    # TODO: decide if we're doing cloud cache
    # cloud_cache_path: str,
    bypass_local_cache: bool,
    logfile: pathlib.Path,
    loglevel: str,
) -> int:
    """Manage the raw data inputs to the C-NEMS input data processing pipeline.

    Download the <placeholder> data:

    datastore <placeholder>

    Download the <placeholder> data only for 2021:

    datastore <placeholder> --partition year=2021

    Re-download the <placeholder> data for 2021 even if you already have it:

    datastore <placeholder> --partition year=2021 --bypass-local-cache

    Validate all California <placeholder> data in the local datastore:

    datastore <placeholder> --validate --partition state=ca

    List the available partitions in the <place1> and <place2> datasets:

    datastore <place1> <place2> --list-partitions

    Download all known datasets (e.g. in automation):

    datastore --all
    """
    import cnems_inputs.logging
    from cnems_inputs.datastore.datastore import (
        Datastore,
        fetch_resources,
        validate_cache,
    )

    logger = cnems_inputs.logging.get_logger(__name__)
    cnems_inputs.logging.configure_root_logger(
        logfile=str(logfile) if logfile else None,
        loglevel=loglevel,  # type: ignore  # noqa: PGH003
    )

    if all_datasets and datasets:
        raise click.UsageError("Cannot combine --all with explicit DATASETS arguments.")
    if not all_datasets and not datasets:
        logger.warning("No datasets specified, nothing to do.")
        return 0

    dataset_list = _KNOWN_DATASETS if all_datasets else list(datasets)

    cache_path = None
    if not bypass_local_cache:
        # TODO: get from environment probably
        cache_path = "./cache"

    dstore = Datastore(
        # cloud_cache_path=cloud_cache_path,
        local_cache_path=cache_path,
    )

    if partition:
        logger.info(f"Only considering resource partitions: {partition}")

    if list_partitions:
        _print_partitions(dstore, dataset_list)
    elif validate:
        validate_cache(dstore, dataset_list, partition)
    else:
        fetch_resources(
            dstore=dstore,
            datasets=dataset_list,
            partition=partition,
            # cloud_cache_path=cloud_cache_path,
            # bypass_local_cache=bypass_local_cache,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
