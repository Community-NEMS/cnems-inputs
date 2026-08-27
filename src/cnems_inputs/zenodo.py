"""Resolve C-NEMS dataset names to Zenodo file URLs."""

import functools
from importlib.resources import files
from pathlib import PurePosixPath
from typing import Annotated
from urllib.parse import quote, urlsplit

import yaml
from pydantic import RootModel, StringConstraints

type ZenodoDoi = Annotated[
    str,
    StringConstraints(pattern=r"^(10\.5072|10\.5281)/zenodo\.([0-9]+)$"),
]


# Validated map from dataset names to Zenodo DOIs.
ZenodoDoiMap = RootModel[dict[str, ZenodoDoi]]


def resolve(
    dataset: str,
    resource_path: str,
    *,
    doi_map: ZenodoDoiMap | None = None,
) -> str:
    """Resolve a known dataset and record-relative path to a Zenodo file URL.

    Spits out a sandbox vs. a prod Zenodo URL based on the DOI.

    By default, dataset names are looked up in ``zenodo_dois.yaml``. Callers can
    pass a ``ZenodoDoiMap`` to override.

    Args:
        dataset: Dataset name configured in the DOI map.
        resource_path: Path to desired resource relative to the dataset's
            Zenodo record.
        doi_map: Optional DOI map to use instead of the default YAML config.

    Returns:
        A public Zenodo file URL.

    Raises:
        KeyError: If the dataset is not configured in the DOI map.
        ValueError: If the relative path is invalid.
        pydantic.ValidationError: If the default YAML config or passed ``doi_map``
            has the wrong shape or includes invalid DOIs.
    """
    doi_config = _default_doi_map() if doi_map is None else doi_map
    file_root = _zenodo_record_url(doi_config.root[dataset])
    path = _normalize_record_path(resource_path)
    return f"{file_root}/files/{quote(path, safe='/')}"


@functools.cache
def _default_doi_map() -> ZenodoDoiMap:
    """Read the default dataset-to-Zenodo-DOI map."""
    config = files("cnems_inputs").joinpath("zenodo_dois.yaml")
    loaded = yaml.safe_load(config.read_text(encoding="utf-8"))
    return ZenodoDoiMap.model_validate(loaded)


def _zenodo_record_url(doi: ZenodoDoi) -> str:
    """Resolve a validated Zenodo DOI to the record's URL."""
    doi_prefix, record_id = doi.split("/zenodo.")
    record_roots = {
        "10.5072": "https://sandbox.zenodo.org",
        "10.5281": "https://zenodo.org",
    }
    return f"{record_roots[doi_prefix]}/records/{record_id}"


def _normalize_record_path(relative_path: str) -> str:
    """Normalize relative paths.

    Reject URLs, absolute paths, empty paths, and paths with .. - those are not
    valid paths for Zenodo file access API.
    """
    path = PurePosixPath(relative_path)
    parsed_url = urlsplit(relative_path)
    if (
        parsed_url.scheme
        or path.is_absolute()
        or path == PurePosixPath(".")
        or ".." in path.parts
    ):
        raise ValueError(f"Zenodo record path must be relative: {relative_path!r}")
    return path.as_posix()
