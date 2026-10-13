"""Resolve pinned datasets and materialize their resources in a local cache."""

import functools
import json
import logging
import shutil
from importlib.resources import files
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated
from urllib.parse import quote, unquote, urlsplit
from urllib.request import urlopen

import s3fs
import yaml
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
        doi_map: ZenodoDoiMap | None = None,
    ) -> None:
        """Configure cache locations and the pinned DOI mapping.

        Set ``s3_cache=None`` to download cache misses directly from Zenodo.
        The DOI mapping defaults to the manually maintained packaged YAML file.
        """
        self.cache_dir = Path(cache_dir)
        self.s3_cache = s3_cache
        self.doi_map = _default_doi_map() if doi_map is None else doi_map
        self._manifests: dict[str, dict] = {}

    def ensure_local(self, dataset: str, resource_name: str) -> Path:
        """Return an existing local copy of the named resource, downloading on miss."""
        relative_path = self._get_resource_path(dataset, resource_name)
        return self._ensure_file(dataset, relative_path)

    def _get_resource_path(self, dataset: str, resource_name: str) -> Path:
        """Return a named resource's relative path from the cached manifest.

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
        return _normalize_record_path(unquote(source.path[len(prefix) :]))

    def _get_manifest(self, dataset: str) -> dict:
        """Cache parsed manifests for this instance's fixed DOI mapping."""
        if dataset not in self._manifests:
            path = self._ensure_file(dataset, "datapackage.json")
            with path.open() as manifest:
                self._manifests[dataset] = json.load(manifest)
        return self._manifests[dataset]

    def _ensure_file(self, dataset: str, relative_path: str | Path) -> Path:
        """Reuse a cached file or publish a download only after it completes."""
        dataset_path = _normalize_record_path(dataset)
        doi = self.doi_map.root[dataset]
        relative_path = _normalize_record_path(relative_path)
        key = dataset_path / doi.replace("/", "-") / relative_path
        destination = self.cache_dir / key
        if destination.is_file():
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
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
        self, dataset: str, relative_path: Path, key: Path, destination: Path
    ) -> None:
        """Download from S3, falling through only on an object-not-found error."""
        if self.s3_cache is not None:
            s3_url = f"{self.s3_cache.rstrip('/')}/{key.as_posix()}"
            logger.info("Fetching %s from S3: %s", relative_path, s3_url)
            try:
                self._download_from_s3(s3_url, destination)
                return
            except FileNotFoundError:
                logger.info("S3 cache miss: %s", s3_url)
        file_root = _zenodo_record_url(self.doi_map.root[dataset])
        url = f"{file_root}/files/{quote(relative_path.as_posix(), safe='/')}"
        logger.info("Fetching %s from Zenodo: %s", relative_path, url)
        self._download_from_zenodo(url, destination)

    def _download_from_s3(self, url: str, destination: Path) -> None:
        """Copy one public S3 object to the given local temporary file."""
        s3fs.S3FileSystem(anon=True).get_file(url, str(destination))

    def _download_from_zenodo(self, url: str, destination: Path) -> None:
        """Stream one pinned Zenodo file to the given local temporary file."""
        with (
            urlopen(url, timeout=30) as source,  # noqa: S310 URL constructed from a validated DOI and relative path.
            destination.open("wb") as target,
        ):
            shutil.copyfileobj(source, target)


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


def _normalize_record_path(relative_path: str | Path) -> Path:
    """Validate and normalize a relative record path for local cache storage.

    Reject URLs, absolute paths, empty paths, and paths with .. since those are not
    valid paths for Zenodo file access API.
    """
    path = Path(relative_path)
    parsed_url = urlsplit(str(relative_path))
    if parsed_url.scheme or path.is_absolute() or path == Path() or ".." in path.parts:
        raise ValueError(f"Zenodo record path must be relative: {relative_path!r}")
    return path
