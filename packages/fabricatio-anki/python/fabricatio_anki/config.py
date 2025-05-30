"""Module containing configuration classes for fabricatio-anki."""
from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class AnkiConfig:
    """Configuration for fabricatio-anki."""



anki_config = CONFIG.load("anki",  AnkiConfig)
__all__ = [
    "anki_config"
]
