"""Module containing configuration classes for fabricatio-character."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class CharacterConfig:
    """Configuration for fabricatio-character."""


character_config = CONFIG.load("character", CharacterConfig)

__all__ = ["character_config"]
