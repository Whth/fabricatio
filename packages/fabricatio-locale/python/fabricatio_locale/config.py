"""Module containing configuration classes for fabricatio-locale."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class LocaleConfig:
    """Configuration for fabricatio-locale."""


locale_config = CONFIG.load("locale", LocaleConfig)
__all__ = ["locale_config"]
