"""Module containing configuration classes for fabricatio-novel."""
from dataclasses import dataclass
from fabricatio_core import CONFIG

@dataclass(frozen=True)
class NovelConfig:
    """ Configuration for fabricatio-novel"""


novel_config = CONFIG.load("novel",  NovelConfig)

__all__ = [
    "novel_config"
]