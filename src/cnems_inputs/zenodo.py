"""Resolve pinned datasets and materialize their resources in a local cache."""

import functools
import json
import logging
import shutil
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated
from urllib.parse import quote, unquote, urlsplit
from urllib.request import urlopen

import s3fs
import yaml
from filelock import FileLock
from pydantic import RootModel, StringConstraints

logger = logging.getLogger(__name__)

type ZenodoDoi = Annotated[
    str,
    StringConstraints(pattern=r"^(10\.5072|10\.5281)/zenodo\.([0-9]+)$"),
]


# Validated map from dataset names to Zenodo DOIs.
ZenodoDoiMap = RootModel[dict[str, ZenodoDoi]]


class DatasetCache:
    """Read pinned manifests and resources from local storage, S3, then Zenodo.

    Local and S3 paths share the layout ``dataset/doi-with-dashes/resource-path``.
    Files in the local cache are complete and treated as immutable. Only local
    storage is written; resources such as ZIPs are returned without extraction.
    """

    def __init__(
        self,
        cache_dir: str | Path = ".snakemake/zenodo",
        *,
        s3_cache: str | None = "s3://pudl.catalyst.coop/zenodo",
        allow_zenodo: bool = True,
        doi_map: ZenodoDoiMap | None = None,
    ) -> None:
        """Configure cache locations and whether misses may fall back to Zenodo.

        Set ``s3_cache=None`` and ``allow_zenodo=False`` for local-only reads.
        The DOI mapping defaults to the manually maintained packaged YAML file.
        """
        self.cache_dir = Path(cache_dir)
        self.s3_cache = s3_cache
        self.allow_zenodo = allow_zenodo
        self.doi_map = _default_doi_map() if doi_map is None else doi_map
        self._manifests: dict[str, dict] = {}

    def ensure_local(self, dataset: str, resource_name: str) -> Path:
        """Return an existing local copy of the named resource, downloading on miss."""
        resource = self.get_resource_metadata(dataset, resource_name)
        return self._ensure_file(dataset, resource.relative_path)

    def get_resource_metadata(
        self, dataset: str, resource_name: str
    ) -> ResourceMetadata:
        """Look up a named resource in the version's cached top-level manifest.

        The manifest's path must be a file URL within the pinned Zenodo record.
        Unknown resources and malformed manifests raise their original errors.
        """
        manifest = self._get_manifest(dataset)
        resource = {r["name"]: r for r in manifest["resources"]}[resource_name]
        source_url = resource["path"]
        file_root = urlsplit(_zenodo_record_url(self.doi_map.root[dataset]))
        source = urlsplit(source_url)
        prefix = f"{file_root.path}/files/"
        if (
            source.scheme != file_root.scheme
            or source.netloc != file_root.netloc
            or not source.path.startswith(prefix)
        ):
            raise ValueError(f"Resource URL is outside the pinned record: {source_url}")
        relative_path = _normalize_record_path(unquote(source.path[len(prefix) :]))
        return ResourceMetadata(resource_name, source_url, relative_path)

    def _get_manifest(self, dataset: str) -> dict:
        """Cache parsed manifests for this instance's fixed DOI mapping."""
        if dataset not in self._manifests:
            path = self._ensure_file(dataset, "datapackage.json")
            with path.open() as manifest:
                self._manifests[dataset] = json.load(manifest)
        return self._manifests[dataset]

    def _ensure_file(self, dataset: str, relative_path: str) -> Path:
        """Publish a complete local file once, coordinating callers across processes."""
        dataset_path = _normalize_record_path(dataset)
        doi = self.doi_map.root[dataset]
        relative_path = _normalize_record_path(relative_path)
        key = f"{dataset_path}/{doi.replace('/', '-')}/{relative_path}"
        destination = self.cache_dir / key
        if destination.is_file():
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(f"{destination}.lock"):
            if destination.is_file():
                return destination
            # Readers only see the final name after the entire download succeeds.
            with NamedTemporaryFile(
                dir=destination.parent, prefix=f".{destination.name}.", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
            try:
                self._download(dataset, relative_path, key, temporary_path)
                temporary_path.replace(destination)
            finally:
                temporary_path.unlink(missing_ok=True)
        return destination

    def _download(
        self, dataset: str, relative_path: str, key: str, destination: Path
    ) -> None:
        """Download from S3, falling through only on an object-not-found error."""
        if self.s3_cache is not None:
            s3_url = f"{self.s3_cache.rstrip('/')}/{key}"
            logger.info("Fetching %s from S3: %s", relative_path, s3_url)
            try:
                s3fs.S3FileSystem(anon=True).get_file(s3_url, str(destination))
                return
            except FileNotFoundError:
                logger.info("S3 cache miss: %s", s3_url)
        if not self.allow_zenodo:
            raise FileNotFoundError(
                f"Resource is not cached and Zenodo is disabled: {key}"
            )
        url = resolve(dataset, relative_path, doi_map=self.doi_map)
        logger.info("Fetching %s from Zenodo: %s", relative_path, url)
        with (
            urlopen(url, timeout=30) as source,  # noqa: S310 URL constructed from a validated DOI and relative path.
            destination.open("wb") as target,
        ):
            shutil.copyfileobj(source, target)


@dataclass(frozen=True)
class ResourceMetadata:
    """A named downloadable file and its equivalent path beneath each cache root."""

    name: str
    source_url: str
    relative_path: str


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


def cache_path(url: str, *, cache_dir: str | Path) -> Path:
    """Return the cached-http cache path for an HTTP(S) URL.

    The cached-http plugin stores files below its configured cache directory using
    the URL netloc and path.
    """
    parsed_url = urlsplit(url)
    return Path(cache_dir) / f"{parsed_url.netloc}{parsed_url.path}"


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

    Reject URLs, absolute paths, empty paths, and paths with .. since those are not
    valid paths for Zenodo file access API.
    """
    path = Path(relative_path)
    parsed_url = urlsplit(relative_path)
    if parsed_url.scheme or path.is_absolute() or path == Path() or ".." in path.parts:
        raise ValueError(f"Zenodo record path must be relative: {relative_path!r}")
    return path.as_posix()
