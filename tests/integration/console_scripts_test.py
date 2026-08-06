"""Test the cnems_inputs console scripts from within PyTest."""

import importlib.metadata

import pytest

# Obtain a list of all deployed entry point scripts to test:
ENTRY_POINTS = importlib.metadata.distribution("cnems_inputs").entry_points


@pytest.mark.parametrize("ep", ENTRY_POINTS)
@pytest.mark.script_launch_mode("inprocess")
def test_console_scripts(script_runner, ep: importlib.metadata.EntryPoint) -> None:
    """Run each deployed console script with --help as a basic test.

    The script_runner fixture is provided by the pytest-console-scripts plugin.
    """
    ret = script_runner.run([ep.name, "--help"], print_result=False)
    assert ret.success  # nosec: B101
