"""Module containing configuration classes for fabricatio-lancedb."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class LancedbConfig:
    """Configuration for fabricatio-lancedb."""


lancedb_config = CONFIG.load("lancedb", LancedbConfig)

__all__ = ["lancedb_config"]
