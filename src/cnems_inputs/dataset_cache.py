"""Cache remote dataset resources locally.

For the dataset to be cached it must:

* be pinned to a Zenodo DOI (see zenodo_dois.yaml)
* have a datapackage.json manifest at the top level

We also have an S3 cache between Zenodo and local, to avoid Zenodo flakiness.
To take advantage of this, the dataset needs to be mirrored by PUDL at
s3://pudl.catalyst.coop/zenodo. If it is not mirrored, we skip the S3 cache
and download the requested resource from Zenodo. It will still be locally
cached.
"""

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
    """

    def __init__(
        self,
        cache_dir: str | Path = ".snakemake/zenodo",
        *,
        s3_cache: str = "s3://pudl.catalyst.coop/zenodo",
        doi_map: ZenodoDoiMap | None = None,
    ) -> None:
        """Configure cache locations and the pinned DOI mapping.

        The DOI mapping defaults to the manually maintained packaged YAML file.
        """
        self.cache_dir: Path = Path(cache_dir)
        self.s3_cache: str = s3_cache
        if doi_map is None:
            config = files("cnems_inputs").joinpath("zenodo_dois.yaml")
            loaded = yaml.safe_load(config.read_text(encoding="utf-8"))
            self.doi_map: ZenodoDoiMap = ZenodoDoiMap.model_validate(loaded)
        else:
            self.doi_map: ZenodoDoiMap = doi_map

    def ensure_local(self, dataset: str, resource_name: str) -> Path:
        """Given dataset and resource name, return a local path to file.

        * Look up the DOI for the dataset
        * If the manifest isn't present locally, retrieve manifest for DOI
        * Read manifest, figure out the relative path of the resource
        * If the file isn't present locally, retrieve the resource from remote
        * Return the path to the local file.
        """
        doi = self.doi_map.root[dataset]
        cache_prefix = _normalize_record_path(dataset) / doi.replace("/", "-")
        record_url = _zenodo_record_url(doi)
        manifest_path = self._ensure_file(cache_prefix, record_url, "datapackage.json")
        manifest = json.loads(manifest_path.read_text())
        relative_path = _get_resource_path(manifest, resource_name, record_url)
        return self._ensure_file(cache_prefix, record_url, relative_path)

    def _ensure_file(
        self, cache_prefix: Path, record_url: str, relative_path: str | Path
    ) -> Path:
        """Cache a file that's in a Zenodo record, locally.

        Downloads first to a temporary file, then swaps once the download is
        done, to avoid partial-download issues.

        Doesn't do the resource-name resolution that ensure_local does, since
        this is blissfully unaware of datapackage.json manifests.

        Args:
            cache_prefix: where we expect the local file to be.
            record_url: the Zenodo URL that is the source of truth for this file
            relative_path: the path relative to the Zenodo record for the
                we want.

        Returns:
            path to the local version of this file
        """
        relative_path = _normalize_record_path(relative_path)
        key = cache_prefix / relative_path
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
            self._download(record_url, relative_path, key, temporary_path)
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)
        return destination

    def _download(
        self, record_url: str, relative_path: Path, key: Path, destination: Path
    ) -> None:
        """Download from S3, fall back to Zenodo.

        Dispatches to backend-specific helpers so we can mock backend
        responses separately in test.
        """
        s3_url = f"{self.s3_cache.rstrip('/')}/{key.as_posix()}"
        logger.info("Fetching %s from S3: %s", relative_path, s3_url)
        try:
            self._download_from_s3(s3_url, destination)
            return
        except FileNotFoundError:
            logger.info("S3 cache miss: %s", s3_url)
        url = f"{record_url}/files/{quote(relative_path.as_posix(), safe='/')}"
        logger.info("Fetching %s from Zenodo: %s", relative_path, url)
        self._download_from_zenodo(url, destination)

    def _download_from_s3(self, url: str, destination: Path) -> None:
        s3fs.S3FileSystem(anon=True).get_file(url, str(destination))

    def _download_from_zenodo(self, url: str, destination: Path) -> None:
        with (
            urlopen(url, timeout=30) as source,  # noqa: S310 URL constructed from a validated DOI and relative path.
            destination.open("wb") as target,
        ):
            shutil.copyfileobj(source, target)


def _get_resource_path(manifest: dict, resource_name: str, record_url: str) -> Path:
    """Extract a named resource's relative path within the pinned record URL.

    Unknown resources and malformed manifests raise their original errors.
    """
    resource = {r["name"]: r for r in manifest["resources"]}[resource_name]
    source_url = resource["path"]
    file_root = urlsplit(record_url)
    source = urlsplit(source_url)
    prefix = f"{file_root.path}/files/"
    if (
        source.scheme != file_root.scheme
        or source.netloc != file_root.netloc
        or not source.path.startswith(prefix)
    ):
        raise ValueError(f"Resource URL is outside the pinned record: {source_url}")
    return _normalize_record_path(unquote(source.path[len(prefix) :]))


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
