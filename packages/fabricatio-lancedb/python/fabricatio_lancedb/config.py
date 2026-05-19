"""Module containing configuration classes for fabricatio-lancedb."""

from dataclasses import dataclass, field

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class LancedbConfig:
    """Configuration for fabricatio-lancedb."""

    database_uri: str = field(default="./lance.db")


lancedb_config = CONFIG.load("lancedb", LancedbConfig)

__all__ = ["lancedb_config"]
