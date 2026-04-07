"""Module containing configuration classes for fabricatio-lod."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class LodConfig:
    """Configuration for fabricatio-lod."""


lod_config = CONFIG.load("lod", LodConfig)

__all__ = ["lod_config"]
