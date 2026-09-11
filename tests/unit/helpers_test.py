"""Test helper functions."""

from cnems_inputs.helpers import versioned_r2_uri


def test_versioned_r2_uri_env_override(monkeypatch):
    monkeypatch.setenv("CNEMS_INPUT_VERSION_ID", "vTest")
    assert versioned_r2_uri("test", "test_path.csv") == "s3://test/vTest/test_path.csv"


def test_versioned_r2_uri_defaults_to_nightly(monkeypatch):
    monkeypatch.delenv("CNEMS_INPUT_VERSION_ID", raising=False)
    assert (
        versioned_r2_uri("test", "test_path.csv") == "s3://test/nightly/test_path.csv"
    )
