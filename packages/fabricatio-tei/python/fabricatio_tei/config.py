"""Module containing configuration classes for fabricatio-tei."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class TeiConfig:
    """Configuration for fabricatio-tei."""


tei_config = CONFIG.load("tei", TeiConfig)

__all__ = ["tei_config"]
