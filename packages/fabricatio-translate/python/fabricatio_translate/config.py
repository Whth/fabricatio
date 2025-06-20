"""Module containing configuration classes for fabricatio-translate."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class TranslateConfig:
    """Configuration for fabricatio-translate."""

    translate_template: str = "translate"
    """The template to use for translation."""


translate_config = CONFIG.load("translate", TranslateConfig)
__all__ = ["translate_config"]
