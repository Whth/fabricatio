"""Module containing configuration classes for fabricatio-diff."""
from dataclasses import dataclass
from fabricatio_core import CONFIG

@dataclass(frozen=True)
class DiffConfig:
    """ Configuration for fabricatio-diff"""

diff_config = CONFIG.load("diff",  DiffConfig)

__all__ = [
    "diff_config"
]