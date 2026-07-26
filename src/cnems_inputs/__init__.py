"""Data pipelines that feed inputs into the Community NEMS project."""

import importlib.metadata
import logging

__author__ = "Catalyst Cooperative"
__contact__ = "pudl@catalyst.coop"
__license__ = "MIT License"
__maintainer_email__ = "pudl@catalyst.coop"
__version__ = importlib.metadata.version("cnems-inputs")

# Create a root logger for use anywhere within the package.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
