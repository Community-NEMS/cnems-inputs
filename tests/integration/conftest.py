"""Set up fake R2 storage and helpers for running resources via Snakemake."""

import functools
import json
import socket
import subprocess
import sysconfig
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from zipfile import ZipFile

import pytest

from cnems_inputs.zenodo import cache_path, resolve


@pytest.fixture(scope="session")
def test_fixture_dir(test_dir: Path) -> Path:
    """Return the test fixture data directory."""
    return test_dir / "fixtures"


@pytest.fixture(scope="session")
def fake_r2(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[Path, dict[str, str]]]:
    """Run an rclone S3-compatible server as a local R2 stand-in."""
    r2_config = {
        "access_key": "local_access_key",
        "bucket": "test-bucket",
        "secret_key": "local_secret_key",  # pragma: allowlist secret
    }

    root = tmp_path_factory.mktemp("fake-r2")
    (root / r2_config["bucket"]).mkdir()

    port = 9001
    r2_config["endpoint_url"] = f"http://127.0.0.1:{port}"

    proc = subprocess.Popen(  # noqa: S603
        [
            str(Path(sysconfig.get_path("scripts")) / "rclone"),
            "serve",
            "s3",
            "--addr",
            f"127.0.0.1:{port}",
            "--config",
            "devenv/rclone.conf",
            "--auth-key",
            f"{r2_config['access_key']},{r2_config['secret_key']}",
            f"local:{root}",
        ],
        text=True,
    )
    try:
        _wait_for_port(port)
        yield root, r2_config
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


@pytest.fixture(scope="session")
def cached_http_cache(
    tmp_path_factory: pytest.TempPathFactory,
    test_fixture_dir: Path,
) -> Path:
    """Warm a Zenodo cache directory with some test inputs.

    This avoids us having to hit Zenodo during integration test. If we pull
    more data from Zenodo we'll have to rethink how we want to warm the cache
    but for now manual creation like this should be OK (2026-09-15).

    We include everything in the test/fixtures/eiabluesky directory, which is
    much less than what's actually archived right now.

    We create the ZIP here so the internal structure of the ZIP is in a
    source-controlled situation instead of opaquely in a committed ZIP file.
    """
    cache_dir = tmp_path_factory.mktemp("cached-http-cache")
    zip_url = resolve("eiabluesky", "eiabluesky-v1-1.zip")
    zip_path = cache_path(zip_url, cache_dir=cache_dir)
    zip_path.parent.mkdir(parents=True)

    source_root = test_fixture_dir / "eiabluesky"
    with ZipFile(zip_path, "w") as zf:
        for source_path in source_root.rglob("*"):
            if source_path.is_file():
                zf.write(
                    source_path,
                    arcname=source_path.relative_to(source_root).as_posix(),
                )

    return cache_dir


@pytest.fixture(scope="session")
def materialize_input(
    fake_r2: tuple[Path, dict[str, str]],
    cached_http_cache: Path,
) -> Callable[[str], Path]:
    """Return a helper that runs Snakemake for one input and returns its CSV.

    Upstream files that you need for your resource, but don't actually want to
    hit network for, should be cached locally via cached_http_cache.

    Points cached_http at the test cache set up in cached_http_cache above so
    we can skip Zenodo.

    Points r2 at the test endpoint set up in fake_r2.
    """

    @functools.cache
    def materialize(resource_name: str) -> Path:
        fake_r2_root, r2_config = fake_r2
        subprocess.run(  # noqa: S603
            [
                str(Path(sysconfig.get_path("scripts")) / "snakemake"),
                "--snakefile",
                "Snakefile",
                "--cores",
                "1",
                "--config",
                "zenodo_source=cache",
                f"cached_http_cache={cached_http_cache.as_posix()}",
                f"r2={json.dumps(r2_config)}",
                "--target-jobs",
                f"extract_from_zip:resource={resource_name}",
            ],
            check=True,
        )

        output_path = (
            fake_r2_root / r2_config["bucket"] / "nightly" / f"{resource_name}.csv"
        )
        assert output_path.exists()
        return output_path

    return materialize


def _wait_for_port(
    port: int,
    *,
    attempts: int = 8,
    initial_delay: float = 0.05,
) -> None:
    """Wait until a localhost TCP port accepts connections."""
    delay = initial_delay
    for _ in range(attempts):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=delay):
                return
        except OSError:
            time.sleep(delay)
            delay *= 2
    raise TimeoutError(f"Timed out waiting for localhost port {port}")
