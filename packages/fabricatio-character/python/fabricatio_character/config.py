"""Module containing configuration classes for fabricatio-character."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class CharacterConfig:
    """Configuration for fabricatio-character."""

    render_character_card_template: str = "built-in/render_character_card"
    """Template to use for rendering character cards."""


character_config = CONFIG.load("character", CharacterConfig)

__all__ = ["character_config"]
