"""Set up fake R2 storage and helpers for running resources via Snakemake."""

import functools
import json
import socket
import subprocess
import sysconfig
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from cnems_inputs.dataset_cache import DatasetCache
from cnems_inputs.helpers import get_published_path_for_resource


@pytest.fixture(scope="session")
def dataset_cache(test_dir: Path) -> DatasetCache:
    """Set up a dataset cache for the test session.

    Grabs datasets by Zenodo DOI from Zenodo mirror hosted on the PUDL S3 bucket.
    If the dataset's not cached on S3, still falls back to Zenodo.
    """
    return DatasetCache(test_dir.parent / ".snakemake" / "zenodo")


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

    port = 9002
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
def materialize_input(
    fake_r2: tuple[Path, dict[str, str]],
    dataset_cache: DatasetCache,
    test_dir,
    config_dir,
) -> Callable[[str], Path]:
    """Return a helper that runs Snakemake for one input and returns its CSV.

    Inputs come from the real S3 mirror through the persistent local dataset cache.
    Only published outputs use the fake R2 endpoint.
    """

    @functools.cache
    def materialize(rule_name: str) -> Path:
        """Materialize one output using the snakemake rule name."""
        fake_r2_root, r2_config = fake_r2
        subprocess.run(  # noqa: S603
            [
                str(Path(sysconfig.get_path("scripts")) / "snakemake"),
                "--snakefile",
                "Snakefile",
                "--cores",
                "1",
                rule_name,
                # snakemake converts lists of int's to str's (wat, mad)
                # in nested dict's passed in with --config. So we need to
                # pass in the whole config inputs plus an override file.
                # https://github.com/snakemake/snakemake/issues/2374
                "--configfiles",
                Path(config_dir, "emm_inputs.yaml"),
                Path(test_dir, "integration", "integration_overrides.yaml"),
                "--config",
                f"dataset_cache_dir={dataset_cache.cache_dir.as_posix()}",
                f"r2={json.dumps(r2_config)}",
            ],
            check=True,
        )

        # this requires all rules to take the form:
        #  - [stage]__[resource_name]
        #  - [stage]__[resource_name]__whatever
        resource_name = rule_name.split("__")[1]
        output_path = (
            fake_r2_root
            / r2_config["bucket"]
            / "nightly"
            # if we ever need to materialize something in integrations that is
            # not a published resource we'll need to revisit this
            / get_published_path_for_resource("datapackage.json", resource_name)
        )
        assert output_path.exists(), (
            f"Expected {rule_name} output at {output_path} but it is not there"
        )
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
