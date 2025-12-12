"""Module containing configuration classes for fabricatio-diff."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class DiffConfig:
    """Configuration for fabricatio-diff."""

    match_precision: float = 1.0
    """Precision threshold for matching."""

    diff_template: str = "built-in/diff"
    """Template string for diff output."""


diff_config = CONFIG.load("diff", DiffConfig)

__all__ = ["diff_config"]
