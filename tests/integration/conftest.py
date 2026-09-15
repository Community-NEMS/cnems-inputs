"""Integration test fixtures for running the Snakemake pipeline."""

import functools
import os
import socket
import subprocess
import sysconfig
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from zipfile import ZipFile

import pytest

from cnems_inputs.zenodo import cache_path, resolve


def _find_free_port() -> int:
    """Return a currently available localhost TCP port."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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


@pytest.fixture(scope="session")
def test_fixture_dir(test_dir: Path) -> Path:
    """Return the test fixture data directory."""
    return test_dir / "fixtures"


@pytest.fixture(scope="session")
def fake_s3(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[dict[str, Path | str]]:
    """Run an rclone S3-compatible server backed by a temporary local directory."""
    access_key = "local_access_key"
    secret_key = "local_secret_key"  # noqa: S105  # pragma: allowlist secret
    bucket = "test-bucket"

    root = tmp_path_factory.mktemp("fake-s3")
    (root / bucket).mkdir()
    port = _find_free_port()
    endpoint_url = f"http://127.0.0.1:{port}"

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
            f"{access_key},{secret_key}",
            f"local:{root}",
        ],
        text=True,
    )
    try:
        _wait_for_port(port)
        yield {
            "access_key": access_key,
            "bucket": bucket,
            "endpoint_url": endpoint_url,
            "root": root,
            "secret_key": secret_key,
        }
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
    """Create a cached Zenodo ZIP containing fixture EMM inputs."""
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
def materialize_emm_input(
    tmp_path_factory: pytest.TempPathFactory,
    fake_s3: dict[str, Path | str],
    cached_http_cache: Path,
) -> Callable[[str], Path]:
    """Return a helper that runs Snakemake for one EMM input and returns its CSV."""

    @functools.cache
    def materialize(resource_name: str) -> Path:
        config_path = tmp_path_factory.mktemp("snakemake-config") / "config.yaml"
        bucket = str(fake_s3["bucket"])
        endpoint_url = str(fake_s3["endpoint_url"])
        config_path.write_text(
            "\n".join(
                [
                    "environment: test",
                    f"cached_http_cache: {cached_http_cache.as_posix()}",
                    "zenodo_source: cache",
                    "r2:",
                    f"  endpoint_url: {endpoint_url}",
                    f"  access_key: {fake_s3['access_key']}",
                    f"  secret_key: {fake_s3['secret_key']}",
                    f"  bucket: {bucket}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.pop("SNAKEMAKE_PROFILE", None)
        version = "pytest"
        env["CNEMS_INPUT_VERSION_ID"] = version
        subprocess.run(  # noqa: S603
            [
                str(Path(sysconfig.get_path("scripts")) / "snakemake"),
                "--snakefile",
                "Snakefile",
                "--configfile",
                str(config_path),
                "--cores",
                "1",
                "--target-jobs",
                f"extract_from_zip:resource={resource_name}",
            ],
            check=True,
            env=env,
        )

        output_path = (
            Path(str(fake_s3["root"])) / bucket / version / f"{resource_name}.csv"
        )
        assert output_path.exists()
        return output_path

    return materialize
